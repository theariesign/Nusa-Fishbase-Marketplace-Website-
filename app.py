from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_login import current_user
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from flask import jsonify
import os
from functools import wraps
from werkzeug.security import check_password_hash
from datetime import datetime
import logging  
import sys
from collections import Counter

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/nusa_fishbase"
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/images/blogkonten')
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = 'your_secret_key'
logging.basicConfig(level=logging.DEBUG)

mongo = PyMongo(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Tolong login dulu ya!, baru bisa nikmati fitur", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/check_login', methods=['GET'])
def check_login():
    if 'email' in session:
        return jsonify({'logged_in': True})
    else:
        return jsonify({'logged_in': False})

@app.route('/get_product_details/<product_id>', methods=['GET'])
def get_product_details(product_id):
    try:
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        product_data = {
            'name': product['name'],
            'price': product['price'],
            'stock': product['stock']
        }
        return jsonify(product_data)
    except Exception as e:
        logging.error(f"Error fetching product details: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching product details'}), 500

@app.route('/')
def home():
    email = session.get('email')
    products = mongo.db.products.find()
    categories = mongo.db.categories.find()
    return render_template('home.html', products=products, categories=categories)

@app.route("/filter_products/<category_name>")
def filter_products(category_name):
    filtered_products = list(mongo.db.products.find({"category": category_name}))
    return render_template("kategori.html", products=filtered_products, category_name=category_name)

@app.route('/riwayat_pembelian')
def riwayat_pembelian():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    
    if not user:
        return redirect(url_for('login'))

    user_id = user['_id']
    purchase_history = mongo.db.riwayat_pembelian.find({'user_email': session['email']})

    riwayat_pembelian = []
    for purchase in purchase_history:
        product_details = {
            'nama_produk': purchase['product_name'],
            'harga': purchase['product_price'],
            'tanggal_pembelian': purchase['purchased_at'].strftime('%Y-%m-%d %H:%M'),  # Ubah format waktu
            'status_pesanan': purchase['status']  # Ubah kunci status sesuai dengan yang benar
        }

        riwayat_pembelian.append(product_details)

    return render_template('riwayat_pembelian.html', riwayat_pembelian=riwayat_pembelian)

@app.route('/blog')
def blog():
    articles = mongo.db.articles.find()
    return render_template('blog.html', articles=articles)

@app.route('/kontak_kami')
def kontak_kami():
    return render_template('kontak_kami.html')

@app.route("/add_to_favorites", methods=["POST"])
def add_to_favorites():
    if 'email' not in session:
        return jsonify({"success": False, "message": "User belum login"})
    
    data = request.json
    user_email = session.get('email')
    
    if not user_email:
        return jsonify({"success": False, "message": "User tidak memiliki email dalam sesi"})
    
    expected_keys = ['product_id', 'image', 'name', 'description', 'price']
    if not all(key in data for key in expected_keys):
        return jsonify({"success": False, "message": "Data yang diterima tidak lengkap atau tidak sesuai format"})
    
    try:
        mongo.db.users.update_one(
            {"email": user_email},
            {"$addToSet": {"favorite_products": data}}
        )
        return jsonify({"success": True, "message": "Produk berhasil ditambahkan ke favorit"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/remove_from_favorites", methods=["POST"])
def remove_from_favorites():
    if 'email' not in session:
        return jsonify({"success": False, "message": "User belum login"})
    
    data = request.json
    user_email = session.get('email')
    
    if not user_email:
        return jsonify({"success": False, "message": "User tidak memiliki email dalam sesi"})
    
    expected_keys = ['product_id']
    if not all(key in data for key in expected_keys):
        return jsonify({"success": False, "message": "Data yang diterima tidak lengkap atau tidak sesuai format"})
    
    try:
        mongo.db.users.update_one(
            {"email": user_email},
            {"$pull": {"favorite_products": {"product_id": data['product_id']}}}
        )
        return jsonify({"success": True, "message": "Produk berhasil dihapus dari favorit"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/favorit")
def favorit():
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']
    user = mongo.db.users.find_one({"email": user_email})
    favorite_products = user.get("favorite_products", [])

    return render_template("favorit.html", favorite_products=favorite_products)

@app.route('/search_results')
def search_results():
    query = request.args.get('query')
    if query:
        search_results = mongo.db.products.find({"name": {"$regex": query, "$options": "i"}})
        products = []
        for product in search_results:
            products.append({
                "_id": str(product["_id"]),
                "name": product["name"],
                "description": product["description"],
                "price": product["price"],
                "stock": product.get("stock", "N/A"),
                "image": url_for('static', filename='images/blogkonten/' + product["image"])
            })
        return render_template('search_results.html', products=products, query=query)
    return render_template('search_results.html', products=[], query=query)
        
@app.route('/cart')
def cart():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        return redirect(url_for('login'))

    cart_items = mongo.db.cart.find_one({'user_id': user['_id']})

    if not cart_items:
        cart_items = {'products': []}

    # Mendapatkan detail produk beserta kuantitasnya
    product_details = []
    product_counter = Counter(cart_items['products'])
    for product_id, quantity in product_counter.items():
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if product:
            product_details.append({
                'product': product,
                'quantity': quantity
            })

    return render_template('cart.html', cart_items=product_details)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'email' not in session:
        return jsonify({'error': 'login_required'}), 401

    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'error': 'product_id_required'}), 400

    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    # Periksa apakah produk sudah ada di keranjang pengguna
    existing_product = mongo.db.cart.find_one(
        {'user_id': user['_id'], 'products': ObjectId(product_id)}
    )

    if existing_product:
        # Jika produk sudah ada di keranjang, tingkatkan jumlahnya
        mongo.db.cart.update_one(
            {'user_id': user['_id'], 'products': ObjectId(product_id)},
            {'$inc': {'quantity': 1}}
        )
    else:
        # Jika produk belum ada di keranjang, tambahkan dengan jumlah 1
        mongo.db.cart.update_one(
            {'user_id': user['_id']},
            {'$addToSet': {'products': ObjectId(product_id)}, '$inc': {'quantity': 1}},
            upsert=True
        )

    return jsonify({'success': True, 'message': 'Produk berhasil ditambahkan ke keranjang'})

@app.route("/buy_now", methods=["POST"])
def buy_now():
    if 'email' not in session:
         return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('product_quantity', 1))
    address = data.get('address', '')

    if not product_id:
        return jsonify({'success': False, 'error': 'Incomplete data'}), 400

    # Ambil data produk dari database
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Cek ketersediaan stok produk
    if product['stock'] < quantity:
        return jsonify({'success': False, 'error': 'Insufficient stock available'}), 400

    total_price = product['price'] * quantity
    purchased_at = datetime.utcnow()

    order_data = {
        'user_email': session['email'],
        'product_id': ObjectId(product_id),
        'product_name': product['name'],
        'product_price': product['price'],
        'product_quantity': quantity,
        'address': address,
        'total_price': total_price,
        'purchased_at': purchased_at,
        'status': 'Menunggu Konfirmasi Penjual'
    }
        
    try:
        # Simpan pesanan ke koleksi orders
        orders_collection = mongo.db.orders
        orders_collection.insert_one(order_data)

        # Simpan pesanan ke koleksi riwayat_pembelian
        riwayat_pembeli_collection = mongo.db.riwayat_pembelian
        riwayat_pembeli_collection.insert_one(order_data)

        # Kurangi stok produk di database
        mongo.db.products.update_one(
            {'_id': ObjectId(product_id)},
            {'$inc': {'stock': -quantity}}
        )

        return jsonify({
            'success': True,
            'message': 'Product has been purchased successfully.'
        })

    except Exception as e:
        error_message = str(e)
        logging.error(f"Error processing buy now: {error_message}")
        return jsonify({'success': False, 'error': 'An error occurred while processing buy now', 'details': error_message}), 500

@app.route("/checkout", methods=["POST"])
def checkout():
    if 'email' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    product_name = data.get('product_name')
    product_price = int(data.get('product_price'))  # Konversi ke integer
    product_quantity = int(data.get('product_quantity'))  # Konversi ke integer
    address = data.get('address', '')

    if not product_id or not product_name or not product_price or not product_quantity:
        return jsonify({'success': False, 'error': 'Incomplete data'}), 400

    total_price = product_price * product_quantity
    
    order_data = {
        'user_email': session['email'],
        'product_id': ObjectId(product_id),
        'product_name': product_name,
        'product_price': product_price,
        'product_quantity': product_quantity,
        'address': address,
        'total_price': total_price,
        'purchased_at': datetime.utcnow(),
        'status': 'Menunggu Konfirmasi Penjual'
    }

    try:
        # Simpan pesanan ke koleksi orders
        orders_collection = mongo.db.orders
        orders_collection.insert_one(order_data)

        # Simpan pesanan ke koleksi riwayat_pembeli
        riwayat_pembeli_collection = mongo.db.riwayat_pembelian
        riwayat_pembeli_collection.insert_one(order_data)

        # Hapus item dari keranjang
        cart_collection = mongo.db.cart
        cart_collection.delete_one({'user_email': session['email'], 'product_id': ObjectId(product_id)})

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    data = request.get_json()
    item_id = data.get('item_id')
    new_quantity = data.get('new_quantity')

    if item_id and new_quantity:
        # Update quantity in cart
        cart_collection = mongo.db.cart
        result = cart_collection.update_one({'_id': ObjectId(item_id)}, {'$set': {'quantity': new_quantity}})

        if result.modified_count == 1:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to update quantity'})
    else:
        return jsonify({'success': False, 'error': 'Invalid data'})

@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():
    try:
        # Dapatkan ID produk yang akan dihapus dari data yang diterima
        product_id = request.json.get('product_id')

        # Hapus produk dari keranjang
        cart_collection = mongo.db.cart
        cart_collection.delete_one({'user_email': session['email'], 'product_id': ObjectId(product_id)})

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/detail_produk/<product_id>')
def detail_produk(product_id):
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if product:
        product_price = product.get('price', 'Price not available')
        return render_template('detail_produk.html', product=product, product_price=product_price)
    else:
        return 'Product not found', 404
    
@app.route("/get_stock_status/<product_id>", methods=["GET"])
def get_stock_status(product_id):
    # Ambil data stok produk dari MongoDB berdasarkan ID produk
    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    
    if product:
        stock_available = product.get("stock", 0) > 0
        return jsonify({"stock_available": stock_available})
    else:
        return jsonify({"error": "Product not found"}), 404
    
@app.route('/pre_order', methods=['POST'])
def pre_order():
    if 'user_id' not in session:
        return jsonify({'message': 'User not logged in.'}), 401
    
    data = request.get_json()
    product_id = data['product_id']
    product_name = data['product_name']
    quantity = data.get('quantity', 1)
    address = data.get('address', '')
    
    # Validasi quantity
    if quantity <= 0:
        return jsonify({'message': 'Invalid quantity.'}), 400
    
    # Ambil data produk dari database
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'message': 'Product not found.'}), 404
    
    product_price = product['price']
    total_price = product_price * quantity
    status = 'pre-order'
    purchased_at = datetime.utcnow()
    
    # Buat entry pre-order di database
    pre_order_data = {
        'user_id': session['user_id'],
        'user_email': session['user_email'],
        'product_id': product_id,
        'product_name': product_name,
        'product_price': product_price,
        'product_quantity': quantity,
        'total_price': total_price,
        'status': status,
        'address': address,
        'purchased_at': purchased_at
    }
    
    # Tambahkan entri ke koleksi riwayat_pembelian
    mongo.db.riwayat_pembelian.insert_one(pre_order_data)
    
    # Tambahkan entri ke koleksi pre_orders
    mongo.db.pre_orders.insert_one(pre_order_data)
    
    return jsonify({'message': 'Pre-order berhasil.', 'success': True})

@app.route('/registrasi', methods=['GET', 'POST'])
def registrasi():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        if mongo.db.users.find_one({"email": email}) or mongo.db.users.find_one({"phone": phone}):
            flash("email atau no telpon anda sudah terdaftar", "danger")
            return redirect(url_for('registrasi'))

        user = {
            "role": role,
            "email": email,
            "phone": phone,
            "password": password,
            "confirmed": False if role == 'penjual' else True
        }
        mongo.db.users.insert_one(user)
        flash("Registrasi berhasil... tunggu konfirmasi dari admin" if role == 'penjual' else "Registrasi sukses. kamu sekarang bisa login.", "success")
        return redirect(url_for('login'))
    return render_template('registrasi.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = mongo.db.users.find_one({"email": email, "password": password})

        if user and user.get('confirmed', False):
            session['logged_in'] = True
            session['email'] = user['email']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                flash("Admin login successful", "success")
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'penjual':
                flash("Penjual login successful", "success")
                return redirect(url_for('penjual_dashboard'))
            else:
                flash("Pembeli login successful", "success")
                return redirect(url_for('home'))
            
        else:
            flash("Maaf akun anda tidak terdaftar!!!", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)
    
@app.route('/edit_profile_pembeli', methods=['GET', 'POST'])
def edit_profile_pembeli():
    if 'email' not in session:
        flash('Anda harus login terlebih dahulu', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')

        mongo.db.users.update_one({'email': session['email']}, {'$set': {'name': name, 'email': email, 'phone': phone, 'address': address}})
        flash('Profil berhasil diperbarui', 'success')
        return redirect(url_for('home'))

    user = mongo.db.users.find_one({'email': session['email']})
    return render_template('edit_profile_pembeli.html', user=user)

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'email' not in session:
        return jsonify({'error': 'login_required'}), 401
    
    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    user_id = user['_id']
    
    # Hapus item keranjang terlebih dahulu
    mongo.db.carts.delete_one({'user_id': ObjectId(user_id)})

    # Hapus pengguna dari database
    mongo.db.users.delete_one({'_id': ObjectId(user_id)})

    # Hapus sesi
    session.clear()
    
    return jsonify({'message': 'Akun anda berhasil dihapus'}), 200


#-----------------------admin----------------------------#

@app.route('/admin_dashboard')
def admin_dashboard():
    if session['role'] != 'admin':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    
    articles = mongo.db.articles.find().sort("published_date", -1)
    unconfirmed_sellers = mongo.db.users.find({"confirmed": False})
    return render_template('admin.html', articles=articles, unconfirmed_sellers=unconfirmed_sellers)

@app.route('/add_blog', methods=['GET', 'POST'])
@login_required
def add_blog():
    if session['role'] != 'admin':
        flash("Only admins can perform this action", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        published_date = request.form.get('published_date')
        image = request.files['image']

        if title and content and published_date and image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            article = {
                "title": title,
                "content": content,
                "published_date": published_date,
                "image": filename
            }
            mongo.db.articles.insert_one(article)
            flash("Artikel berhasil di tambahkan", "success")
            return redirect(url_for('manage_blog'))
        else:
            flash("Failed to add article. Please fill in all fields.", "danger")

    return render_template('add_blog.html')

@app.route('/edit_article/<article_id>', methods=['GET', 'POST'])
def edit_article(article_id):
    article = mongo.db.articles.find_one({'_id': ObjectId(article_id)})
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        published_date = request.form['published_date']
        image = request.files['image']
        
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            mongo.db.articles.update_one({'_id': ObjectId(article_id)}, {'$set': {
                'title': title,
                'content': content,
                'published_date': published_date,
                'image': filename
            }})
        else:
            mongo.db.articles.update_one({'_id': ObjectId(article_id)}, {'$set': {
                'title': title,
                'content': content,
                'published_date': published_date
            }})
        flash('Article updated successfully!', 'success')
        return redirect(url_for('manage_blog'))
    return render_template('edit_article.html', article=article)

@app.route('/delete_article/<article_id>', methods=['POST'])
def delete_article(article_id):
    mongo.db.articles.delete_one({'_id': ObjectId(article_id)})
    flash('Article deleted successfully!', 'success')
    return redirect(url_for('manage_blog'))

@app.route('/manage_blog')
def manage_blog():
    articles = mongo.db.articles.find()
    return render_template('manage_blog.html', articles=articles)

@app.route('/manage_seller')
@login_required
def manage_seller():
    unconfirmed_sellers = mongo.db.users.find({'confirmed': False})
    return render_template('manage_seller.html', unconfirmed_sellers=unconfirmed_sellers)

@app.route('/confirm_seller/<user_id>')
@login_required
def confirm_seller(user_id):
    mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'confirmed': True}})
    flash('Seller confirmed successfully!', 'success')
    return redirect(url_for('manage_seller'))

@app.route('/manage_distributor')
def manage_distributors():
    distributors = mongo.db.distributors.find()
    return render_template('manage_distributors.html', distributors=distributors)

@app.route('/edit_distributor/<distributor_id>', methods=['GET', 'POST'])
def edit_distributor(distributor_id):
    distributor = mongo.db.distributors.find_one({'_id': ObjectId(distributor_id)})
    if request.method == 'POST':
        nama_restoran = request.form['nama_restoran']
        alamat = request.form['alamat']
        kontak = request.form['kontak']
        image = request.files['image']
        
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            mongo.db.distributors.update_one({'_id': ObjectId(distributor_id)}, {'$set': {
                'nama_restoran': nama_restoran,
                'alamat': alamat,
                'kontak': kontak,
                'image': filename
            }})
        else:
            mongo.db.distributors.update_one({'_id': ObjectId(distributor_id)}, {'$set': {
                'nama_restoran': nama_restoran,
                'alamat': alamat,
                'kontak': kontak
            }})
        flash('Distributor updated successfully!', 'success')
        return redirect(url_for('manage_distributors'))
    return render_template('edit_distributor.html', distributor=distributor)

@app.route('/add_distributor', methods=['GET', 'POST'])
def add_distributor():
    if request.method == 'POST':
        # Ambil data dari form
        nama_restoran = request.form['nama_restoran']
        alamat = request.form['alamat']
        kontak = request.form['kontak']
        image = request.files['image']

        # Cek apakah file gambar diunggah
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
        else:
            filename = 'default.png'  # Jika tidak ada gambar diunggah, gunakan default

        # Simpan data distributor ke database
        mongo.db.distributors.insert_one({
            'nama_restoran': nama_restoran,
            'alamat': alamat,
            'kontak': kontak,
            'image': filename
        })
        flash('Distributor added successfully!', 'success')
        return redirect(url_for('manage_distributors'))
    return render_template('tambah_distributor.html')

@app.route('/delete_distributor/<distributor_id>', methods=['POST'])
def delete_distributor(distributor_id):
    mongo.db.distributors.delete_one({'_id': ObjectId(distributor_id)})
    flash('Distributor deleted successfully!', 'success')
    return redirect(url_for('manage_distributors'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#----------------penjual-------------------#

@app.route('/penjual_dashboard')
@login_required
def penjual_dashboard():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    
    # Get the email of the logged-in seller
    seller_email = session['email']
    
    # Find orders containing products added by the seller
    seller_orders = mongo.db.users.find({"seller_email": seller_email})
    return render_template('dashboard_penjual.html')

@app.route('/profil_penjual')
def profil_penjual():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))

    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    profile = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    
    return render_template('profil_penjual.html', profile=profile)

def get_seller_profile(email):
    return mongo.db.users.find_one({'email': email})

# Fungsi untuk memperbarui data profil penjual di MongoDB
def update_seller_profile(email, phone_number):
    mongo.db.users.update_one({'email': email}, {'$set': {'phone_number': phone_number}})
    # Anda dapat menambahkan operasi pembaruan lain sesuai kebutuhan

@app.route('/edit_profil', methods=['GET', 'POST'])
def edit_profil():
    if 'email' not in session:
        flash('Anda harus login terlebih dahulu', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        # Panggil fungsi untuk memperbarui profil penjual di MongoDB
        update_seller_profile(session['email'], phone_number)
        flash('Profil berhasil diperbarui', 'success')
        return redirect(url_for('seller_profile'))  # Redirect kembali ke halaman profil penjual setelah mengedit

    # Dapatkan data profil penjual dan kirimkan ke template
    seller_profile = get_seller_profile(session['email'])
    return render_template('edit_profil.html', seller=seller_profile)
    
@app.route('/orders')
def show_orders():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    
    # Get the email of the logged-in seller
    seller_email = session['email']
    
    # Ambil daftar pesanan dari database MongoDB
    orders = mongo.db.orders.find()

    # Kirimkan daftar pesanan ke template untuk ditampilkan
    return render_template('orders.html', orders=orders)

@app.route('/update_status/<order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    new_status = request.form.get('status')
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})

    if not order:
        flash('Pesanan tidak ditemukan', 'error')
        return redirect(url_for('orders'))

    # Perbarui status pesanan
    mongo.db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})

    if new_status == 'pesanan dibatalkan':
        # Simpan data pesanan yang dibatalkan ke dalam koleksi sales
        sale_data = {
            'buyer': order.get('buyer_email'),
            'product_name': order.get('product_name'),
            'quantity': order.get('quantity'),
            'date': datetime.utcnow(),
            'product_id': order.get('product_id'),
            'status': 'Pesanan dibatalkan'
        }
        mongo.db.sales.insert_one(sale_data)

        # Simpan data pesanan yang dibatalkan ke dalam koleksi riwayat_pembelian
        purchase_history_data = {
            'buyer': order.get('buyer_email'),
            'product_name': order.get('product_name'),
            'quantity': order.get('quantity'),
            'date': datetime.utcnow(),
            'product_id': order.get('product_id'),
            'status': 'Pesanan dibatalkan'
        }
        mongo.db.riwayat_pembelian.insert_one(purchase_history_data)

        # Hapus pesanan dari koleksi orders
        mongo.db.orders.delete_one({'_id': ObjectId(order_id)})

        flash('Pesanan telah dibatalkan', 'success')
        return redirect(url_for('sales_history'))

    # Update status in riwayat_pembelian
    mongo.db.riwayat_pembelian.update_one(
    {'_id': ObjectId(order_id)},
    {'$set': {'status': new_status}},
    upsert=True  # Menambahkan jika tidak ada dokumen yang cocok
)

    flash('Status pesanan berhasil diperbarui', 'success')
    return redirect(url_for('orders'))

@app.route('/sales_history')
@login_required
def sales_history():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    
    # Get the email of the logged-in seller
    seller_email = session['email']
    
    # Find orders containing products added by the seller
    sales = mongo.db.sales.find({"seller_email": seller_email})
    
    return render_template('sales_history.html', sales=sales)


@app.route('/confirm_order/<order_id>')
@login_required
def confirm_order(order_id):
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    
    if not order:
        flash('Pesanan tidak ditemukan', 'error')
        return redirect(url_for('show_orders'))
    
    new_status = 'pesanan diterima penjual'
    mongo.db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})
    
    # Update status in riwayat_pembelian
    mongo.db.riwayat_pembelian.update_one(
        {'_id': ObjectId(order_id)},
        {'$set': {'status': new_status}},
        upsert=True  # Menambahkan jika tidak ada dokumen yang cocok
    )
    
    flash('Pesanan telah diterima oleh penjual', 'success')
    return redirect(url_for('show_orders'))

@app.route('/cancel_order/<order_id>')
@login_required
def cancel_order(order_id):
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    
    if not order:
        flash('Pesanan tidak ditemukan', 'error')
        return redirect(url_for('show_orders'))
    
    new_status = 'pesanan dibatalkan'
    mongo.db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})
    
    # Simpan data pesanan yang dibatalkan ke dalam koleksi sales
    sale_data = {
        'buyer': order.get('buyer_email'),
        'product_name': order.get('product_name'),
        'quantity': order.get('quantity'),
        'date': datetime.utcnow(),
        'product_id': order.get('product_id'),
        'status': new_status
    }
    mongo.db.sales.insert_one(sale_data)
    
    # Simpan data pesanan yang dibatalkan ke dalam koleksi riwayat_pembelian
    purchase_history_data = {
        'buyer': order.get('buyer_email'),
        'product_name': order.get('product_name'),
        'quantity': order.get('quantity'),
        'date': datetime.utcnow(),
        'product_id': order.get('product_id'),
        'status': new_status
    }
    mongo.db.riwayat_pembelian.insert_one(purchase_history_data)
    
    # Hapus pesanan dari koleksi orders
    mongo.db.orders.delete_one({'_id': ObjectId(order_id)})
    
    flash('Pesanan telah dibatalkan', 'success')
    return redirect(url_for('show_orders'))

@app.route('/produk')
@login_required
def produk():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    # Add logic to handle product management here
    products = mongo.db.products.find({"seller": session['email']})
    return render_template('produk.html', products=products)

@app.route('/produk/add', methods=['GET', 'POST'])
@login_required
def add_produk():
    if session['role'] != 'penjual':
        flash("Only sellers can perform this action", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        stock = request.form.get('stock')  # Menambahkan input untuk stok produk
        image = request.files['image']
        
        if image:
            filename = secure_filename(image.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'])
            
            # Create directory if it doesn't exist
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            
            image.save(os.path.join(upload_path, filename))

            product = {
                "name": name,
                "description": description,
                "price": price,
                "stock": stock,  # Menyimpan nilai stok dalam objek produk
                "image": filename,
                "seller": session['email']
            }
            mongo.db.products.insert_one(product)
            flash("Produk berhasil di tambahkan", "success")
        else:
            flash("Failed to add product. Image is required.", "danger")
        
        return redirect(url_for('produk'))

    return render_template('add_produk.html')

@app.route('/produk/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_produk(product_id):
    if session['role'] != 'penjual':
        flash("Only sellers can perform this action", "danger")
        return redirect(url_for('home'))

    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        stock = request.form.get('stock')
        image = request.files.get('image')

        update_data = {
            "name": name,
            "description": description,
            "price": price,
            "stock": stock
        }

        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            update_data["image"] = filename

        mongo.db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )
        
        flash("data produk berhasil di update", "success")
        return redirect(url_for('produk'))
    
    return render_template('edit_produk.html', product=product)


@app.route('/produk/delete/<product_id>')
@login_required
def delete_produk(product_id):
    if session['role'] != 'penjual':
        flash("Only sellers can perform this action", "danger")
        return redirect(url_for('home'))

    mongo.db.products.delete_one({"_id": ObjectId(product_id)})
    flash("Produk berhasil di hapus", "success")
    return redirect(url_for('produk'))

@app.route('/orders')
@login_required
def orders():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    
    # Get the email of the logged-in seller
    seller_email = session['email']
    
    # Find orders containing products added by the seller
    orders = mongo.db.orders.find({"seller_email": seller_email})
    
    return render_template('orders.html', orders=orders)

@app.route('/distributors')
@login_required
def distributor():
    if session['role'] != 'penjual':
        flash("Only sellers can access this page", "danger")
        return redirect(url_for('home'))
    # Add logic to show distributor channels here
    distributors = mongo.db.distributors.find()
    return render_template('distributors.html', distributors=distributors)

if __name__ == '__main__':
     app.run(debug=True)
