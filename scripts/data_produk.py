import hashlib
import hmac
import time
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.config import XL_API_CONFIG
import logging
from core.database import get_db_connection
from models.data_produk import XLProduct

logger = logging.getLogger(__name__)

def create_session():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def get_xl_products(kategori=None):
    """Fetch XL products from API with improved error handling"""
    timestamp = str(int(time.time()))
    string_to_sign = f"{XL_API_CONFIG['username']}:{timestamp}"
    signature = hmac.new(
        XL_API_CONFIG['api_key'].encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'X-API-USERNAME': XL_API_CONFIG['username'],
        'X-TIMESTAMP': timestamp,
        'X-SIGNATURE': signature,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    data = {}
    if kategori:
        data['kategori'] = kategori
        logger.info(f"Fetching products for category: {kategori}")
    else:
        logger.info("Fetching all products")
    
    # Buat URL lengkap dengan menggabungkan base_url dan endpoint produk
    api_url = f"{XL_API_CONFIG['base_url']}produk"
    logger.debug(f"API Request - URL: {api_url}, Headers: {headers}, Data: {data}")
    
    session = create_session()
    try:
        response = session.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10
        )
        response.raise_for_status()
        response_data = response.json()
        
        # Log response summary
        if 'data' in response_data:
            product_count = len(response_data['data'])
            logger.info(f"API Response: Received {product_count} products")
            
            # Log first few products as sample
            if product_count > 0:
                sample_size = min(3, product_count)
                sample_products = response_data['data'][:sample_size]
                logger.debug(f"Sample products: {json.dumps(sample_products, indent=2)}")
        else:
            logger.warning(f"API Response: No 'data' field in response. Response: {response_data}")
        
        return response_data
        
    except requests.exceptions.SSLError as e:
        logger.error(f"SSL Error: {e}")
        # Try without SSL verification as fallback
        logger.info("Attempting fallback request without SSL verification")
        try:
            response = session.post(
                api_url,
                headers=headers,
                json=data,
                timeout=10,
                verify=False
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Log response summary for fallback
            if 'data' in response_data:
                product_count = len(response_data['data'])
                logger.info(f"Fallback API Response: Received {product_count} products")
            else:
                logger.warning(f"Fallback API Response: No 'data' field in response. Response: {response_data}")
            
            return response_data
            
        except Exception as fallback_e:
            logger.error(f"Fallback request failed: {fallback_e}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected API Error: {e}")
        return None

def is_product_active(status):
    """Check if product status is considered active
    
    Args:
        status (str): Product status from API
        
    Returns:
        bool: True if status is active, False otherwise
    """
    if not status:
        return False
    
    status_lower = str(status).lower().strip()
    active_statuses = ['aktif', 'active', '1', 'true', 'on', 'enabled']
    
    return status_lower in active_statuses

def sync_products_with_api(kategori=None):
    """Synchronize products with API - only keep active products in database
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Statistics of synchronization (inserted, updated, deleted, errors)
    """
    # Get products from API
    response = get_xl_products(kategori)
    if not response:
        logger.error("Failed to fetch products from XL API (null response)")
        return {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 1}
    
    if 'data' not in response:
        logger.error(f"Invalid API response format. Response keys: {list(response.keys())}")
        return {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 1}
    
    api_products = response.get('data', [])
    product_count = len(api_products)
    
    if product_count == 0:
        logger.info("No products found in API response")
        # Jika tidak ada produk dari API, hapus semua produk di database
        return delete_all_products(kategori)
    
    logger.info(f"Starting synchronization with {product_count} products from API")
    
    stats = {
        'inserted': 0,
        'updated': 0,
        'deleted': 0,
        'errors': 0
    }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Filter hanya produk aktif dari API
        active_api_products = []
        inactive_count = 0
        
        for product_data in api_products:
            status = product_data.get('status', 'aktif')
            if is_product_active(status):
                active_api_products.append(product_data)
            else:
                inactive_count += 1
                logger.debug(f"Skipping inactive product: {product_data.get('produk_code')} (status: {status})")
        
        logger.info(f"Found {len(active_api_products)} active products and {inactive_count} inactive products in API")
        
        # Ambil semua produk code yang aktif di API
        active_api_product_codes = set()
        for product_data in active_api_products:
            produk_code = product_data.get('produk_code') or product_data.get('kode_produk')
            if produk_code:
                active_api_product_codes.add(produk_code)
        
        logger.info(f"API memiliki {len(active_api_product_codes)} produk aktif dengan kode valid")
        
        # Ambil semua produk code yang ada di database
        if kategori:
            cursor.execute("SELECT produk_code FROM data_xl WHERE kategori = %s", (kategori,))
        else:
            cursor.execute("SELECT produk_code FROM data_xl")
        
        db_product_codes = set(row['produk_code'] for row in cursor.fetchall())
        logger.info(f"Database memiliki {len(db_product_codes)} produk")
        
        # Cari produk yang ada di database tapi tidak ada di API aktif (harus dihapus)
        # Ini termasuk produk yang tidak ada di API sama sekali ATAU produk yang statusnya tidak aktif
        products_to_delete = db_product_codes - active_api_product_codes
        
        if products_to_delete:
            logger.info(f"Menghapus {len(products_to_delete)} produk yang tidak aktif atau tidak ada di API")
            
            # Hapus produk yang tidak aktif atau tidak ada di API
            for produk_code in products_to_delete:
                try:
                    cursor.execute("DELETE FROM data_xl WHERE produk_code = %s", (produk_code,))
                    if cursor.rowcount > 0:
                        stats['deleted'] += 1
                        logger.info(f"Produk dihapus: {produk_code}")
                except Exception as e:
                    logger.error(f"Error menghapus produk {produk_code}: {e}")
                    stats['errors'] += 1
        
        # Proses setiap produk aktif dari API (hanya tambah yang baru)
        for product_data in active_api_products:
            try:
                produk_code = product_data.get('produk_code') or product_data.get('kode_produk')
                if not produk_code:
                    logger.warning(f"Produk tanpa kode diabaikan: {product_data}")
                    continue
                
                # Cek apakah produk sudah ada di database
                cursor.execute("SELECT id FROM data_xl WHERE produk_code = %s", (produk_code,))
                existing_product = cursor.fetchone()
                
                if not existing_product:
                    # Produk baru, tambahkan ke database
                    result = add_new_product_from_api(product_data, cursor)
                    if result:
                        stats['inserted'] += 1
                        logger.info(f"Produk aktif baru ditambahkan: {produk_code}")
                    else:
                        stats['errors'] += 1
                else:
                    # Produk sudah ada, tidak perlu diupdate (sesuai permintaan)
                    logger.debug(f"Produk aktif sudah ada, diabaikan: {produk_code}")
                    stats['updated'] += 1  # Count as updated for tracking
                    
            except Exception as e:
                product_code = product_data.get('produk_code') or product_data.get('kode_produk', 'unknown')
                logger.error(f"Error memproses produk {product_code}: {e}")
                stats['errors'] += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Log category summary (hanya produk aktif)
        categories = {}
        for product_data in active_api_products:
            kategori_produk = product_data.get('kategori', 'Unknown')
            if kategori_produk not in categories:
                categories[kategori_produk] = 0
            categories[kategori_produk] += 1
        
        logger.info("Active product categories summary:")
        for category, count in categories.items():
            logger.info(f" - {category}: {count} products")
        
        logger.info(f"Synchronization completed. "
                   f"Inserted: {stats['inserted']}, "
                   f"Existing: {stats['updated']}, "
                   f"Deleted: {stats['deleted']}, "
                   f"Errors: {stats['errors']}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error dalam sinkronisasi produk: {e}")
        stats['errors'] += 1
        return stats

def add_new_product_from_api(product_data, cursor):
    """Add new product from API to database (only if active)
    
    Args:
        product_data (dict): Product data from API
        cursor: Database cursor
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from datetime import datetime
        
        # Cek status produk terlebih dahulu
        status = product_data.get('status', 'aktif')
        if not is_product_active(status):
            logger.warning(f"Tidak menambahkan produk tidak aktif: {product_data.get('produk_code')} (status: {status})")
            return False
        
        # Ekstrak data produk dari respons API
        nama_produk = product_data.get('nama_produk')
        kategori = product_data.get('kategori')
        produk_code = product_data.get('produk_code') or product_data.get('kode_produk')
        
        # Konversi harga dari string ke float jika perlu
        harga_panel_str = product_data.get('harga_panel', '0.00')
        try:
            harga_panel = float(harga_panel_str)
        except (ValueError, TypeError):
            logger.warning(f"Gagal mengkonversi harga_panel: {harga_panel_str}")
            harga_panel = 0.0
        
        # harga_bayar biasanya sudah dalam bentuk integer
        harga_bayar = product_data.get('harga_bayar', 0)
        
        # Deskripsi dari API
        deskripsi = product_data.get('deskripsi', '')
        
        # Normalisasi status ke 'aktif' (karena sudah difilter sebelumnya)
        status_normalized = 'aktif'
        
        # Validasi field yang diperlukan
        if not all([nama_produk, produk_code, kategori]):
            logger.error(f"Field yang diperlukan tidak lengkap: {product_data}")
            return False
        
        # Hitung harga jual (10% dari harga panel)
        harga_jual = round(harga_panel * 1.1)
        
        now = datetime.now()
        
        # Insert produk baru
        cursor.execute("""
            INSERT INTO data_xl (nama_produk, kategori, produk_code, 
                               harga_panel, harga_bayar, harga_jual, deskripsi, status,
                               created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (nama_produk, kategori, produk_code, harga_panel, harga_bayar,
              harga_jual, deskripsi, status_normalized, now, now))
        
        return True
        
    except Exception as e:
        logger.error(f"Error menambahkan produk baru: {e}")
        return False

def delete_all_products(kategori=None):
    """Delete all products in database (used when API returns no products)
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Statistics of deletion
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if kategori:
            cursor.execute("DELETE FROM data_xl WHERE kategori = %s", (kategori,))
            logger.info(f"Menghapus semua produk dalam kategori: {kategori}")
        else:
            cursor.execute("DELETE FROM data_xl")
            logger.info("Menghapus semua produk (tidak ada produk di API response)")
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dihapus {deleted_count} produk")
        
        return {
            'inserted': 0,
            'updated': 0,
            'deleted': deleted_count,
            'errors': 0
        }
        
    except Exception as e:
        logger.error(f"Error menghapus produk: {e}")
        return {
            'inserted': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 1
        }

def update_product_database(kategori=None):
    """Legacy function - now calls sync_products_with_api for backward compatibility
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        tuple: (success_count, error_count, new_count, updated_count)
    """
    stats = sync_products_with_api(kategori)
    success_count = stats['inserted'] + stats['updated']
    error_count = stats['errors']
    new_count = stats['inserted']
    updated_count = stats['updated']
    
    return success_count, error_count, new_count, updated_count

def get_sync_summary(stats):
    """Generate a summary of synchronization results
    
    Args:
        stats (dict): Synchronization statistics
        
    Returns:
        str: Formatted summary string
    """
    summary_lines = []
    summary_lines.append("=== PRODUCT SYNCHRONIZATION SUMMARY ===")
    
    if stats['inserted'] > 0:
        summary_lines.append(f"✅ New active products added: {stats['inserted']}")
    
    if stats['updated'] > 0:
        summary_lines.append(f"📋 Existing active products found: {stats['updated']}")
    
    if stats['deleted'] > 0:
        summary_lines.append(f"🗑️ Products deleted (inactive/not in API): {stats['deleted']}")
    
    if stats['errors'] > 0:
        summary_lines.append(f"⚠️ Errors encountered: {stats['errors']}")
    
    total_processed = stats['inserted'] + stats['updated'] + stats['deleted']
    summary_lines.append(f"📊 Total processed: {total_processed}")
    
    if stats['errors'] == 0 and total_processed > 0:
        summary_lines.append("✅ Synchronization completed successfully!")
    elif stats['errors'] > 0:
        summary_lines.append("⚠️ Synchronization completed with some errors.")
    else:
        summary_lines.append("📝 No changes were needed.")
    
    summary_lines.append("=" * 40)
    return "\n".join(summary_lines)

def force_full_sync():
    """Force a complete synchronization of all products
    
    Returns:
        dict: Synchronization statistics
    """
    logger.info("Starting forced full synchronization...")
    # Get all products from API and sync
    stats = sync_products_with_api()
    return stats

def get_product_comparison_report(kategori=None):
    """Generate a detailed comparison report between API and database
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Detailed comparison report
    """
    try:
        # Get products from API
        response = get_xl_products(kategori)
        if not response or 'data' not in response:
            logger.error("Failed to get API products for comparison")
            return None

        api_products = response.get('data', [])
        
        # Separate active and inactive products from API
        active_api_codes = set()
        inactive_api_codes = set()
        api_products_dict = {}
        api_status_count = {'aktif': 0, 'non-aktif': 0}
        
        for product in api_products:
            code = product.get('produk_code') or product.get('kode_produk')
            if code:
                api_products_dict[code] = product
                
                # Check if product is active
                status = product.get('status', 'aktif')
                if is_product_active(status):
                    active_api_codes.add(code)
                    api_status_count['aktif'] += 1
                else:
                    inactive_api_codes.add(code)
                    api_status_count['non-aktif'] += 1

        # Get products from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if kategori:
            cursor.execute("SELECT * FROM data_xl WHERE kategori = %s", (kategori,))
        else:
            cursor.execute("SELECT * FROM data_xl")
        
        db_products = cursor.fetchall()
        db_codes = set(product['produk_code'] for product in db_products)
        db_products_dict = {product['produk_code']: product for product in db_products}
        
        cursor.close()
        conn.close()

        # Generate comparison report
        report = {
            'api_total': len(api_products),
            'api_active': len(active_api_codes),
            'api_inactive': len(inactive_api_codes),
            'db_total': len(db_codes),
            'only_active_in_api': list(active_api_codes - db_codes),
            'only_in_db': list(db_codes - active_api_codes),
            'in_both_active': list(active_api_codes & db_codes),
            'inactive_in_api': list(inactive_api_codes),
            'api_status_count': api_status_count,
            'categories': {},
            'sync_actions': {
                'will_add': len(active_api_codes - db_codes),
                'will_keep': len(active_api_codes & db_codes),
                'will_delete': len(db_codes - active_api_codes)
            }
        }

        # Category breakdown (only active products)
        for product in api_products:
            if product.get('produk_code') in active_api_codes:
                cat = product.get('kategori', 'Unknown')
                if cat not in report['categories']:
                    report['categories'][cat] = 0
                report['categories'][cat] += 1

        logger.info(f"Comparison Report:")
        logger.info(f"- API products: {report['api_total']} (aktif: {api_status_count['aktif']}, non-aktif: {api_status_count['non-aktif']})")
        logger.info(f"- DB products: {report['db_total']}")
        logger.info(f"- Will add: {report['sync_actions']['will_add']} new active products")
        logger.info(f"- Will keep: {report['sync_actions']['will_keep']} existing active products")
        logger.info(f"- Will delete: {report['sync_actions']['will_delete']} products (inactive or not in API)")
        logger.info(f"- Inactive in API (will be ignored): {len(report['inactive_in_api'])}")

        return report

    except Exception as e:
        logger.error(f"Error generating comparison report: {e}")
        return None

def dry_run_sync(kategori=None):
    """Perform a dry run of synchronization without making changes
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: What would happen in a real sync
    """
    logger.info("Starting dry run synchronization...")
    
    try:
        # Get products from API
        response = get_xl_products(kategori)
        if not response or 'data' not in response:
            logger.error("Failed to get API products for dry run")
            return {'would_insert': 0, 'would_delete': 0, 'existing': 0, 'ignored_inactive': 0, 'errors': 1}

        api_products = response.get('data', [])
        
        # Filter only active products from API
        active_api_codes = set()
        inactive_count = 0
        
        for product in api_products:
            code = product.get('produk_code') or product.get('kode_produk')
            if code:
                status = product.get('status', 'aktif')
                if is_product_active(status):
                    active_api_codes.add(code)
                else:
                    inactive_count += 1

        # Get products from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if kategori:
            cursor.execute("SELECT produk_code FROM data_xl WHERE kategori = %s", (kategori,))
        else:
            cursor.execute("SELECT produk_code FROM data_xl")
        
        db_codes = set(row['produk_code'] for row in cursor.fetchall())
        
        cursor.close()
        conn.close()

        # Calculate what would happen
        would_insert = len(active_api_codes - db_codes)
        would_delete = len(db_codes - active_api_codes)
        existing = len(active_api_codes & db_codes)
        
        result = {
            'would_insert': would_insert,
            'would_delete': would_delete,
            'existing': existing,
            'ignored_inactive': inactive_count,
            'errors': 0
        }

        logger.info(f"Dry run results:")
        logger.info(f"- Would insert: {would_insert} new active products")
        logger.info(f"- Would delete: {would_delete} products (inactive or not in API)")
        logger.info(f"- Would keep: {existing} existing active products")
        logger.info(f"- Would ignore: {inactive_count} inactive products from API")

        return result

    except Exception as e:
        logger.error(f"Error in dry run: {e}")
        return {'would_insert': 0, 'would_delete': 0, 'existing': 0, 'ignored_inactive': 0, 'errors': 1}

def get_product_status_report(kategori=None):
    """Generate a detailed status report of products in database
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Detailed status report
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Base query
        base_query = "SELECT kategori, status, COUNT(*) as count FROM data_xl"
        params = []
        
        if kategori:
            base_query += " WHERE kategori = %s"
            params.append(kategori)
        
        base_query += " GROUP BY kategori, status ORDER BY kategori, status"
        
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        
        # Get total counts
        total_query = "SELECT COUNT(*) as total FROM data_xl"
        if kategori:
            total_query += " WHERE kategori = %s"
            cursor.execute(total_query, params)
        else:
            cursor.execute(total_query)
        
        total_products = cursor.fetchone()['total']
        
        # Get status summary
        status_query = "SELECT status, COUNT(*) as count FROM data_xl"
        if kategori:
            status_query += " WHERE kategori = %s"
        status_query += " GROUP BY status"
        
        cursor.execute(status_query, params)
        status_summary = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format report
        report = {
            'total_products': total_products,
            'category_filter': kategori,
            'status_summary': {item['status']: item['count'] for item in status_summary},
            'category_breakdown': {},
            'last_updated': None
        }
        
        # Group by category
        for item in results:
            cat = item['kategori']
            if cat not in report['category_breakdown']:
                report['category_breakdown'][cat] = {}
            report['category_breakdown'][cat][item['status']] = item['count']
        
        # Get last update time
        last_update_query = "SELECT MAX(updated_at) as last_update FROM data_xl"
        if kategori:
            last_update_query += " WHERE kategori = %s"
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(last_update_query, params)
        last_update = cursor.fetchone()
        if last_update and last_update['last_update']:
            report['last_updated'] = last_update['last_update'].isoformat()
        
        cursor.close()
        conn.close()
        
        logger.info("Product Status Report (Database):")
        logger.info(f"- Total products: {total_products}")
        for status, count in report['status_summary'].items():
            logger.info(f"- {status}: {count}")
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating status report: {e}")
        return None

def backup_products_before_sync(kategori=None):
    """Create a backup of current products before synchronization
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        str: Backup file path or None if failed
    """
    try:
        import os
        from datetime import datetime
        
        # Create backup directory if it doesn't exist
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if kategori:
            backup_file = f"{backup_dir}/products_backup_{kategori}_{timestamp}.json"
        else:
            backup_file = f"{backup_dir}/products_backup_all_{timestamp}.json"
        
        # Get current products from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if kategori:
            cursor.execute("SELECT * FROM data_xl WHERE kategori = %s", (kategori,))
        else:
            cursor.execute("SELECT * FROM data_xl")
        
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert datetime objects to strings for JSON serialization
        for product in products:
            if product.get('created_at'):
                product['created_at'] = product['created_at'].isoformat()
            if product.get('updated_at'):
                product['updated_at'] = product['updated_at'].isoformat()
        
        # Save to backup file
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump({
                'backup_date': datetime.now().isoformat(),
                'category': kategori,
                'total_products': len(products),
                'products': products
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Backup created: {backup_file} ({len(products)} products)")
        return backup_file
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def sync_with_backup(kategori=None):
    """Perform synchronization with automatic backup
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Synchronization statistics with backup info
    """
    logger.info("Starting synchronization with backup...")
    
    # Create backup first
    backup_file = backup_products_before_sync(kategori)
    
    # Perform synchronization
    stats = sync_products_with_api(kategori)
    
    # Add backup info to stats
    stats['backup_file'] = backup_file
    
    if backup_file:
        logger.info(f"Synchronization completed with backup: {backup_file}")
    else:
        logger.warning("Synchronization completed but backup failed")
    
    return stats

def cleanup_old_backups(days_to_keep=7):
    """Clean up old backup files
    
    Args:
        days_to_keep (int): Number of days to keep backup files
        
    Returns:
        dict: Cleanup statistics
    """
    try:
        import os
        from datetime import datetime, timedelta
        
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            return {'deleted': 0, 'errors': 0}
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        error_count = 0
        
        for filename in os.listdir(backup_dir):
            if filename.startswith('products_backup_') and filename.endswith('.json'):
                file_path = os.path.join(backup_dir, filename)
                try:
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting backup {filename}: {e}")
                    error_count += 1
        
        logger.info(f"Backup cleanup completed: {deleted_count} files deleted, {error_count} errors")
        return {'deleted': deleted_count, 'errors': error_count}
        
    except Exception as e:
        logger.error(f"Error in backup cleanup: {e}")
        return {'deleted': 0, 'errors': 1}

def get_api_status_breakdown(kategori=None):
    """Get detailed breakdown of product statuses from API
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Status breakdown from API
    """
    try:
        response = get_xl_products(kategori)
        if not response or 'data' not in response:
            logger.error("Failed to get API products for status breakdown")
            return None

        api_products = response.get('data', [])
        
        status_breakdown = {
            'total': len(api_products),
            'active': 0,
            'inactive': 0,
            'status_details': {},
            'categories': {}
        }
        
        for product in api_products:
            status = product.get('status', 'aktif')
            kategori_produk = product.get('kategori', 'Unknown')
            
            # Count by normalized status
            if is_product_active(status):
                status_breakdown['active'] += 1
            else:
                status_breakdown['inactive'] += 1
            
            # Count by exact status
            if status not in status_breakdown['status_details']:
                status_breakdown['status_details'][status] = 0
            status_breakdown['status_details'][status] += 1
            
            # Count by category (only active products)
            if is_product_active(status):
                if kategori_produk not in status_breakdown['categories']:
                    status_breakdown['categories'][kategori_produk] = 0
                status_breakdown['categories'][kategori_produk] += 1
        
        logger.info("API Status Breakdown:")
        logger.info(f"- Total: {status_breakdown['total']}")
        logger.info(f"- Active: {status_breakdown['active']}")
        logger.info(f"- Inactive: {status_breakdown['inactive']}")
        logger.info(f"- Status details: {status_breakdown['status_details']}")
        
        return status_breakdown
        
    except Exception as e:
        logger.error(f"Error getting API status breakdown: {e}")
        return None

def validate_sync_integrity(kategori=None):
    """Validate the integrity of synchronization by comparing API active products with DB
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Integrity validation report
    """
    try:
        logger.info("Starting sync integrity validation...")
        
        # Get active products from API
        response = get_xl_products(kategori)
        if not response or 'data' not in response:
            logger.error("Failed to get API products for validation")
            return None

        api_products = response.get('data', [])
        active_api_codes = set()
        
        for product in api_products:
            code = product.get('produk_code') or product.get('kode_produk')
            status = product.get('status', 'aktif')
            if code and is_product_active(status):
                active_api_codes.add(code)
        
        # Get products from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if kategori:
            cursor.execute("SELECT produk_code, status FROM data_xl WHERE kategori = %s", (kategori,))
        else:
            cursor.execute("SELECT produk_code, status FROM data_xl")
        
        db_products = cursor.fetchall()
        db_codes = set(product['produk_code'] for product in db_products)
        
        cursor.close()
        conn.close()
        
        # Validate integrity
        validation_report = {
            'api_active_count': len(active_api_codes),
            'db_count': len(db_codes),
            'missing_in_db': list(active_api_codes - db_codes),
            'extra_in_db': list(db_codes - active_api_codes),
            'in_sync': len(active_api_codes - db_codes) == 0 and len(db_codes - active_api_codes) == 0,
            'sync_percentage': 0
        }
        
        if len(active_api_codes) > 0:
            matching_count = len(active_api_codes & db_codes)
            validation_report['sync_percentage'] = (matching_count / len(active_api_codes)) * 100
        
        logger.info("Sync Integrity Validation:")
        logger.info(f"- API active products: {validation_report['api_active_count']}")
        logger.info(f"- DB products: {validation_report['db_count']}")
        logger.info(f"- Missing in DB: {len(validation_report['missing_in_db'])}")
        logger.info(f"- Extra in DB: {len(validation_report['extra_in_db'])}")
        logger.info(f"- Sync percentage: {validation_report['sync_percentage']:.2f}%")
        logger.info(f"- In sync: {validation_report['in_sync']}")
        
        return validation_report
        
    except Exception as e:
        logger.error(f"Error in sync integrity validation: {e}")
        return None

def get_detailed_sync_report(kategori=None):
    """Generate a comprehensive sync report combining multiple data sources
    
    Args:
        kategori (str, optional): Category to filter products. Defaults to None.
        
    Returns:
        dict: Comprehensive sync report
    """
    try:
        logger.info("Generating detailed sync report...")
        
        report = {
            'timestamp': time.time(),
            'category_filter': kategori,
            'api_status': None,
            'db_status': None,
            'comparison': None,
            'integrity': None,
            'dry_run': None
        }
        
        # Get API status breakdown
        report['api_status'] = get_api_status_breakdown(kategori)
        
        # Get DB status report
        report['db_status'] = get_product_status_report(kategori)
        
        # Get comparison report
        report['comparison'] = get_product_comparison_report(kategori)
        
        # Validate integrity
        report['integrity'] = validate_sync_integrity(kategori)
        
        # Get dry run results
        report['dry_run'] = dry_run_sync(kategori)
        
        logger.info("Detailed sync report generated successfully")
        return report
        
    except Exception as e:
        logger.error(f"Error generating detailed sync report: {e}")
        return None

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # If run directly, perform comprehensive analysis and sync
    start_time = time.time()
    logger.info("Starting comprehensive product synchronization...")
    
    # 1. Generate detailed report before sync
    logger.info("=== PRE-SYNC ANALYSIS ===")
    pre_sync_report = get_detailed_sync_report()
    
    if pre_sync_report:
        print("Pre-sync Summary:")
        if pre_sync_report['api_status']:
            api_status = pre_sync_report['api_status']
            print(f"- API: {api_status['total']} total ({api_status['active']} active, {api_status['inactive']} inactive)")
        
        if pre_sync_report['db_status']:
            db_status = pre_sync_report['db_status']
            print(f"- DB: {db_status['total_products']} total")
        
        if pre_sync_report['dry_run']:
            dry_run = pre_sync_report['dry_run']
            print(f"- Dry run: +{dry_run['would_insert']} -{dry_run['would_delete']} ={dry_run['existing']} (ignore {dry_run['ignored_inactive']})")
        
        if pre_sync_report['integrity']:
            integrity = pre_sync_report['integrity']
            print(f"- Current sync: {integrity['sync_percentage']:.1f}% ({integrity['in_sync']})")
    
    # 2. Perform actual sync with backup
    logger.info("=== PERFORMING SYNC ===")
    stats = sync_with_backup()
    
    # 3. Post-sync validation
    logger.info("=== POST-SYNC VALIDATION ===")
    post_sync_integrity = validate_sync_integrity()
    
    elapsed_time = time.time() - start_time
    
    # 4. Print comprehensive summary
    print("\n" + get_sync_summary(stats))
    
    if post_sync_integrity:
        print(f"Post-sync integrity: {post_sync_integrity['sync_percentage']:.1f}% "
              f"({post_sync_integrity['in_sync']})")
    
    logger.info(f"Complete synchronization finished in {elapsed_time:.2f} seconds")
    
    if stats.get('backup_file'):
        print(f"Backup saved to: {stats['backup_file']}")
    
    # 5. Cleanup old backups (optional)
    logger.info("=== CLEANUP OLD BACKUPS ===")
    cleanup_stats = cleanup_old_backups(days_to_keep=7)
    if cleanup_stats['deleted'] > 0:
        print(f"Cleaned up {cleanup_stats['deleted']} old backup files")
    
    # 6. Final status report
    logger.info("=== FINAL STATUS ===")
    final_status = get_product_status_report()
    if final_status:
        print(f"Final DB status: {final_status['status_summary']}")
