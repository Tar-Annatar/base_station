import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Run after every request


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User comes in and submits data
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 400)
        # Ensure
        elif not request.form.get("confirmation"):
            return apology("Must provide password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match", 400)
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        # EXECUTE TO ENSURE NO USERNAME REPEATS
        if (len(rows) > 0):
            return apology("That username is taken bro", 400)
        else:
            hashed_password = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users(username, hash) VALUES (?,?)",
                       request.form.get("username"), hashed_password)
            # return apology("GG", 403)
            return redirect("/")
    # GET route - came here by clicking "Register" button
    else:
        return render_template("register.html")


# Run for root URL (The layout HTML)
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    users = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])
    owned_cash = round(users[0]['cash'], 2)
    dict_pt2 = db.execute("""SELECT symbol, sum(shares) as sum_of_shares
                            FROM purchases
                            WHERE id = ?
                            GROUP BY id, symbol
                            HAVING sum_of_shares > 0""", session["user_id"])

    dict_pt2 = [dict(x, **{'price': round(lookup(x['symbol'])['price'], 2)}) for x in dict_pt2]
    dict_pt2 = [dict(x, **{'total': round(x['price'] * x['sum_of_shares'], 2)}) for x in dict_pt2]

    absolute_total = round(float(owned_cash + sum([x['total'] for x in dict_pt2])), 2)
    return render_template("index.html", owned=owned_cash, dict=dict_pt2, totals=absolute_total)


# Run for getting stock name;
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # If you are submitting data
    if request.method == "POST":
        if not request.form.get("symbol").upper():
            return apology("Must provide a symbol", 400)
        quote = lookup(request.form.get("symbol").upper())
        if not quote:
            return apology("Provide a correct symbol please", 400)
        # name = quote.name
        name = quote["name"]
        price = round(quote["price"], 2)
        # price = round(quote.price, 2)
        if not quote:
            return apology("Provide a correct symbol please", 400)
        return render_template("quoted.html", quote=quote, name=name, price=price)

    # If you got to the page through a link
    else:
        return render_template("quote.html")


# Run for buy url
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # When submitting data from this site
    if request.method == "POST":
        if not request.form.get("symbol").upper():
            return apology("Must provide a symbol", 400)
        if not request.form.get("shares"):
            return apology("Must provide shares", 400)
        if (request.form.get("shares")).isdigit() == False:
            return apology("Must provide integer value for shares", 400)
        quote = lookup(request.form.get("symbol").upper())
        if not quote:
            return apology("Provide a correct symbol please", 400)
        user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
        cash = user[0]["cash"]
        share_value = int(quote["price"])
        total = share_value * int(request.form.get("shares"))
        if total > cash:
            return apology("You're too poor bro", 400)
        elif total < cash:
            db.execute("INSERT INTO purchases(id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                       session["user_id"], request.form.get("symbol").upper(), request.form.get("shares"), quote["price"])
            db.execute("UPDATE users SET cash = ? WHERE id = ?;",
                       int(cash - total), session["user_id"])
            flash("Bought!")
            return redirect("/")
        else:
            return render_template("buy.html")

    # When getting to the site via a link (GET)
    else:
        return render_template("buy.html")
    # return apology("TODO")


# Run for selling stocks
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    owned_stuff = db.execute("""SELECT symbol, sum(shares) as sum_of_shares
                                FROM purchases
                                WHERE id = ?
                                GROUP BY id, symbol
                                HAVING sum_of_shares > 0""", session["user_id"])
    the_dict = {d['symbol']: d['sum_of_shares'] for d in owned_stuff}
    if request.method == "POST":
        if not (symbol := request.form.get("symbol")):
            return apology("MISSING SYMBOL", 400)
        if not (shares := request.form.get("shares")):
            return apology("MISSING SHARES", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("INVALID SHARES", 400)

        if not (shares > 0):
            return apology("INVALID SHARES", 400)
        elif the_dict[symbol] < shares:
            return apology("TOO MANY SHARES", 400)

        query = lookup(symbol)
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        money = rows[0]['cash'] + (query['price'] * shares)
        db.execute("INSERT INTO purchases(id, symbol, shares, price) VALUES(?, ?, ?, ?);",
                   session["user_id"], symbol, -shares, query["price"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?;",
                   money, session["user_id"])
        flash("Sold!")
        return redirect("/")
    else:
        return render_template("sell.html", symbols=owned_stuff)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM purchases WHERE id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    if request.method == "POST":
        if not request.form.get("password"):
            return apology("Must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("Must provide password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match", 400)
        new_password_hash = generate_password_hash(request.form.get("password"))
        # Update the password in the "users" table
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_password_hash, session["user_id"])
        return redirect("/")
    else:
        return render_template("change.html")
