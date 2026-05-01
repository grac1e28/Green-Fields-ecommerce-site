# Imports
from flask import Flask, render_template, request, flash, session, get_flashed_messages, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
import re
import os

# Create Application
app = Flask(__name__)
app.secret_key = "secret_key"

# Configer SQL database
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Data tables

class Users(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(15), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(100), unique=True, nullable=False)
    loyalty_points = db.Column(db.Integer, default=0)
    logged_in = db.Column(db.Boolean, default=False)
    is_farmer = db.Column(db.Boolean, default=False)

class Farms(db.Model):
    farmer_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    farm_name = db.Column(db.String(30), unique=True, nullable=False)
    farm_description = db.Column(db.String(200), nullable=False)
    farm_location = db.Column(db.String(100))
    img_url = db.Column(db.String(2000))

class Products(db.Model):
    product_id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer)
    product_name = db.Column(db.String(30), nullable=False)
    product_category = db.Column(db.String(30), nullable=False)
    product_description = db.Column(db.String(200), nullable=False)
    img_url = db.Column(db.String(2000))
    product_price = db.Column(db.Float(5), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

class Orders(db.Model):
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    order_type = db.Column(db.String(20), nullable=False)
    scheduled = db.Column(db.String)
    address = db.Column(db.String(255))

class OrderItems(db.Model):
    order_items_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    product_name = db.Column(db.String(100))
    item_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

# Website routing

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        email = request.form.get("email")
        # Can store this and send emails out in future
    products = Products.query.all()
    return render_template("index.html", products=products)
    
@app.route("/about-us")
def aboutUs():
    return render_template("aboutUs.html")

@app.route("/privacy-policy")
def privacyPolicy():
    return render_template("privacyPolicy.html")

@app.route("/faq")
def faq():
    return render_template("faq.html")

@app.route("/producers")
def producers():
    farms = Farms.query.all()
    return render_template("producers.html", farms=farms)

@app.route("/shop-produce")
def shopProduce():

    selected_category = request.args.get('category')

    all_products = Products.query.all()
    categories = []

    for p in all_products:
        if p.product_category and p.product_category not in categories:
            categories.append(p.product_category)

    categories.sort()

    if selected_category:
        display_products =Products.query.filter_by(product_category=selected_category).all()
    else:
        display_products = all_products
    
    
    return render_template("shopProduce.html", products=display_products, categories=categories)

@app.route("/update-cart", methods=["POST"])
def update_cart():
    item_id = request.json.get("item_id")
    quantity = request.json.get("quantity")

    item = OrderItems.query.get(item_id)

    if item:
        if quantity <= 0:
            db.session.delete(item)
        else:
            item.quantity = quantity

        db.session.commit()

    return {"success": True}

# Add to cart
@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in", "info")
        return redirect(url_for("login"))

    user = Users.query.get(user_id)
    if not user or not user.logged_in:
        flash("You must log in", "info")
        return redirect(url_for("login"))

    product_id = request.form["product_id"]
    quantity = int(request.form.get("quantity", 1))

    product = Products.query.get(product_id)
    if not product:
        flash("Item Not Found", "error")
        return redirect(url_for("shopProduce"))

    # cart order
    order = Orders.query.filter_by(
        user_id=user_id,
        order_type="cart"
    ).first()

    if not order:
        order = Orders(
            user_id=user_id,
            total_price=0,
            order_type="cart"
        )
        db.session.add(order)
        db.session.commit()

    existing_item = OrderItems.query.filter_by(
        order_id=order.order_id,
        product_id=product.product_id
    ).first()

    if existing_item:
        existing_item.quantity += quantity
    else:
        new_item = OrderItems(
            order_id=order.order_id,
            product_id=product.product_id,
            product_name=product.product_name,
            item_price=product.product_price,
            quantity=quantity
        )
        db.session.add(new_item)

    db.session.commit()

    flash("Item Added To Cart!", "success")
    return redirect(url_for("shopProduce"))

# Cart
@app.route("/cart")
def cart():
    # Checks user is logged in
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    user = Users.query.get(user_id)
    if not user or not user.logged_in:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    #COllects users by id
    orders = Orders.query.filter_by(user_id=user_id, order_type="cart").all()

    total = 0
    cart_data = []

    # In every order
    for order in orders:

        # Collect items by user id
        items = OrderItems.query.filter_by(order_id=order.order_id).all()

        order_items = []

        #Each item that the user has added to basket
        for item in items:
            #get product
            product = Products.query.get(item.product_id)
            #update subtotal
            sub_total = float(item.item_price) * item.quantity
            #add to total
            total += sub_total

            #adds items to list
            order_items.append({
                "item_id": item.order_items_id,
                "product_name": product.product_name,
                "img_url": product.img_url,
                "price": float(item.item_price),
                "quantity": item.quantity,
                "sub_total": sub_total
            })

        #adds all data to list to be loaded
        cart_data.append({
            "order_id": order.order_id,
            "order_items": order_items
        })

    return render_template("cart.html",
                           cart_data=cart_data,
                           total=total)

# Checkout

@app.route("/checkout", methods=["GET", "POST"])
def checkout(): 
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    user = Users.query.get(user_id)
    if not user or not user.logged_in:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))
 
    # cart order
    cart_order = Orders.query.filter_by(user_id=user_id, order_type="cart").first()

    if not cart_order:
        flash("No active cart", "error")
        return redirect(url_for("cart"))

    # total from items
    items = OrderItems.query.filter_by(order_id=cart_order.order_id).all()

    total = 0
    for item in items:
        total += float(item.item_price) * item.quantity

    if request.method == "POST":
        # form data
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        email = request.form.get("email")

        #doesnt return an empty string if not entered
        def clean(value):
            return value.strip() if value else None
        delivery_type = request.form.get("delivery_type")
        post_code = clean(request.form.get("postCode"))
        house_number = clean(request.form.get("houseNumberName"))
        street = clean(request.form.get("streetName"))
        county = clean(request.form.get("county"))
        country = clean(request.form.get("country"))
        time_frame = request.form.get("timeFrame") or None
        # does not save to database as would impliment a more secure way of doing this in further developments

        order = Orders(
            user_id=user_id,
            total_price=total,
            order_type=delivery_type,
            scheduled=time_frame,
            address=post_code
        )

        db.session.add(order)
        db.session.commit()

        # discount
        if user.loyalty_points > 1000:
            discount = total * 0.1
            total -= discount
            flash("Discount Applied!", "success")

        # loyalty points
        earned_pts = int(total * 10)
        user.loyalty_points += earned_pts

        # transport ongoing
        cart_order.order_type = "ongoing"
        cart_order.total_price = total

        db.session.commit()

        flash(f"You earned {earned_pts} loyalty points!", "success")

        # new empty cart
        new_cart = Orders(
            user_id=user_id,
            total_price=0,
            order_type="cart"
        )
        db.session.add(new_cart)
        db.session.commit()

        return redirect(url_for("userDashboard"))

    return render_template("checkout.html", total=total, user=user)


# Uder Dash
@app.route("/user-dashboard")
def userDashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    user = Users.query.get(user_id)
    if not user or not user.logged_in:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))
    

    # Fetch ongoing orders for this user
    ongoing_orders = Orders.query.filter_by(user_id=user_id, order_type='ongoing').all()
    
    # Fetch completed orders for this user
    completed_orders = Orders.query.filter_by(user_id=user_id, order_type='completed').all()

    # Fetch delivery address of order
    delivery_address = Orders.query.filter_by(user_id=user_id).all()

    # Fetch users loyalty points
    loyalty_pts = user.loyalty_points
    
    # Attach items and product info to each order
    def attach_items(orders):
        for order in orders:
            order.items = OrderItems.query.filter_by(order_id=order.order_id).all()
            for item in order.items:
                item.product = Products.query.get(item.product_id)
        return orders

    ongoing_orders = attach_items(ongoing_orders)
    completed_orders = attach_items(completed_orders)
    
    return render_template('userDashboard.html',
        current_user=user,
        ongoing_orders=ongoing_orders,
        completed_orders=completed_orders,
        loyalty_pts=loyalty_pts,
        address=delivery_address
    )

#Farm dash
@app.route("/farm-dashboard", methods = ["GET", "POST"])
def farmDashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    user = Users.query.get(user_id)
    if not user or not user.logged_in:
        flash("You must log in to view the shop", "info")
        return redirect(url_for("login"))

    revenue = "1,000"
    ongoing_orders = "6"
    complete_orders = "19"

    #filter products by the farm_id
    # farm_id = the id when logged in as a farm
    products = Products.query.all()

    if request.method == "POST":
        
        img_url = request.files.get("img_url")
        product_name = request.form.get("product_name")
        product_description = request.form.get("product_description")
        stock = request.form.get("stock")
        product_price = request.form.get("product_price")
        product_category = request.form.get("product_category")

        # Save file
        if img_url:
            filename = secure_filename(img_url.filename)

            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            img_url.save(filepath)
            allowed_extention = {"png", "jpg", "jpeg", "webp"}

            img_path = f"/static/uploads/{filename}"

        else:
            img_path = None

        # Error checks too many decimals and rounds
        if float(product_price) is not None:
            product_price = round(float(product_price), 2)

        # Product len check
        if len(product_name) < 3 or len(product_name) > 30:
            flash("Product Name Too Long!", "error")
            return redirect(url_for("farmDashboard"))
        
        # Category len check
        if len(product_description) < 3 or len(product_description) > 200:
            flash("Product Description Too Long!", "error")
            return redirect(url_for("farmDashboard"))

        # Presence check
        if not product_name or not product_description or not stock or not product_price or not product_category or not img_url:
            flash("Please fill in all inputs", "error")
            return redirect(url_for("farmDashboard"))

        # Check product Duplicate
        existing_product = Products.query.filter_by(product_name=product_name).first()

        if existing_product:
            flash("An existing product already has this name.", "error")
            return redirect(url_for("farmDashboard"))
        
        # Add product to database
        product = Products(
            farmer_id=user_id,
            img_url = img_path,
            product_name = product_name,
            product_description = product_description,
            stock = stock,
            product_price = product_price,
            product_category = product_category
        )
        
        db.session.add(product)
        db.session.commit()
        flash("Successfully added product to database", "success")

        return redirect(url_for("farmDashboard"))
    return render_template("farmDashboard.html",
                           revenue=revenue,
                           ongoing_orders=ongoing_orders,
                           complete_orders=complete_orders,
                           products=products)

# delete a specific product
@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    product = Products.query.get_or_404(product_id)

    db.session.delete(product)
    db.session.commit()

    return redirect(url_for("farmDashboard"))

# edit a specific product
@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    product = Products.query.get_or_404(product_id)

    if request.method == "POST":
        product.product_name = request.form.get("product_name")
        product.product_description = request.form.get("product_description")
        product.stock = request.form.get("stock")
        product.product_price = request.form.get("product_price")
        product.product_category = request.form.get("product_category")

        db.session.commit()

        return redirect(url_for("farmDashboard"))

    return render_template("editProduct.html", product=product)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        
        name = request.form.get("name")
        password = request.form.get("password")
        confirm = request.form.get("cfmPassword")
        email = request.form.get("email")
        userType = request.form.get("user_type")
        terms = request.form.get("terms")

        #Password Match Check
        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("signup"))
        
        # Password type check
        caps = sum(1 for c in password if c.isupper())
        nums = sum(1 for c in password if c.isdigit())
        symb = any(c in password for c in '!@#$%^&')
        if len(password) <7:
            flash("Password must be more then 6 characters", "error")
            return redirect(url_for("signup"))
        elif caps < 1:
            flash("Password must have at least one capital", "error")
            return redirect(url_for("signup"))
        elif nums < 1:
            flash("Password must have at least one number", "error")
            return redirect(url_for("signup"))
        elif symb == False:
            flash("Password must include a symbol", "error")
            return redirect(url_for("signup"))
        

        # Presence check
        if not name or not password or not confirm or not email or not userType or not terms:
            flash("Please fill in all inputs", "error")
            return redirect(url_for("signup"))

        # Length Check
        if len(name) <3 or len(name) > 30:
            flash("Name must be bettween 3 and 30 characters", "error")
            return redirect(url_for("signup"))
        
        # Email validation
        regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(regex, email):
            flash("Email is not a valid format", "error")
            return redirect(url_for("signup"))
        
        # Check Email Duplicate
        existing_user = Users.query.filter_by(user_email=email).first()

        if existing_user:
            flash("Email already registered" , "info")
            return redirect(url_for("signup"))
        
        # Add all users to user database
        user = Users(
            user_name=name,
            password_hash=generate_password_hash(password),
            user_email=email)
        
        db.session.add(user)
        db.session.commit()
        flash("Successfully added to database", "success")

        # if farmer, add to farmer db
        if userType == "farmer":
            farm_name = request.form.get("farm-name")
            farm_description = request.form.get("farm-description")
            farm_location = request.form.get("farm-location")
            img_url = request.files.get("farm-img")
            if img_url:
                # save the file
                filename = secure_filename(img_url.filename)
                img_url.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                img_url = filename

            if not farm_name or not farm_description:
                flash("Please provide farm name and description", "error")
                return redirect(url_for("signup"))

            farm = Farms(
                user_id=user.user_id,
                farm_name=farm_name,
                farm_description=farm_description,
                farm_location=farm_location
            )
            db.session.add(farm)
            db.session.commit()
            flash("Farmer account created successfully!", "success")
        else:
            flash("User account created successfully!", "success")

        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        
        name = request.form.get("name")
        password = request.form.get("password")
        email = request.form.get("email")
        userType = request.form.get("user_type")

        # Presence check
        if not name or not password or not email:
            flash("Please fill in all inputs", "error")
            return redirect(url_for("login"))
        
        # Check for user
        user = Users.query.filter_by(user_email=email).first()
        if not user:
            flash("No account found with that email", "error")
            return redirect(url_for("login"))
        
        # check password
        if not check_password_hash(user.password_hash, password):
            flash("Incorrect password", "error")
            return redirect(url_for("login"))
        
        user.logged_in = True
        db.session.commit()

        # stores id in session
        session["user_id"] = user.user_id

        flash("Successfully logged in!", "success")

        # Check if farmer
        farm = Farms.query.filter_by(user_id=user.user_id).first()
        session["is_farmer"] = bool(farm)

        if farm:
            return redirect(url_for("farmDashboard"))
        else:
            return redirect(url_for("userDashboard"))
        
    return render_template("login.html")

@app.route("/logout")
def logout():
    user_id = session.get("user_id")

    if user_id:
        user = Users.query.get(user_id)
        if user:
            user.logged_in = False
            db.session.commit()

    session.clear()

    flash("Logged out successfully", "success")
    return redirect(url_for("home"))

# Run Code
if __name__ == "__main__":
    with app.app_context():
        #db.drop_all()
        db.create_all()

        # PRODUCTS TEMPORARY DATA
        if Products.query.count() == 0:
            p1 = Products (product_name = "apple",
            product_description = "crunchy",
            stock = 60,
            product_price = 1.50,
            product_category = "fruit",
            img_url = "static/apple.webp")

            p2 = Products (product_name = "Eggs",
            product_description = "fresh",
            stock = 60,
            product_price = 1.50,
            product_category = "dairy",
            img_url = "static/eggs.webp")

            p3 = Products (product_name = "Ham",
            product_description = "juicy",
            stock = 60,
            product_price = 1.50,
            product_category = "meat",
            img_url = "static/ham.webp")
    
            db.session.add_all([p1, p2, p3])
            db.session.commit()

        #FARMERS TEMPORARY DATA
        if Farms.query.count() == 0:
            f1 = Farms (farm_name = "farm1",
            farm_description = "friendly",
            farm_location = "westlands",
            img_url = "static/farm-placeholder.jpg",
            )

            f2 = Farms (farm_name = "Greenscape Farm",
            farm_description = "A small, family run farm that has run for decades. We pride ourselfs with the high quality meat and dairy products we provide through dedication and hard work. ",
            farm_location = "The Hills",
            img_url = "static/farm-placeholder.jpg",
            )

            f3 = Farms (farm_name = "farm3",
            farm_description = "freindly ",
            farm_location = "westlands",
            img_url = "static/farm-placeholder.jpg",
            )
    
            db.session.add_all([f1, f2, f3])
            db.session.commit()


    
    app.run(debug=True)