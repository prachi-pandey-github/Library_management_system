from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flashing messages

# MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="library_db"
    )

@app.route('/')
def home():
    return render_template('frontend/index.html')

# Add Book
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        book_name = request.form['book_name']
        author_name = request.form['author_name']
        subject = request.form['subject']
        copies = int(request.form['copies'])

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the book exists
        cursor.execute("SELECT * FROM books_collection WHERE book_name = %s AND author_name = %s AND subject = %s",
                       (book_name, author_name, subject))
        book = cursor.fetchone()

        if book:
            # If the book already exists, check if additional copies are provided
            additional_copies = request.form.get('additional_copies')
            if additional_copies:
                additional_copies = int(additional_copies)
                cursor.execute("UPDATE books_collection SET available_copies = available_copies + %s WHERE book_id = %s",
                               (additional_copies, book[0]))
                flash(f"Added {additional_copies} more copies of '{book_name}'.", "success")
            else:
                flash(f"The book '{book_name}' already exists in the collection.", "warning")
        else:
            # If the book does not exist, add it to the collection
            cursor.execute("INSERT INTO books_collection (book_name, subject, author_name, available_copies) VALUES (%s, %s, %s, %s)",
                           (book_name, subject, author_name, copies))
            flash(f"Added new book '{book_name}' to the collection.", "success")

        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template('frontend/add_book.html', book_exists=False)

@app.route('/issue_book', methods=['GET', 'POST'])
def issue_book():
    if request.method == 'POST':
        book_name = request.form['book_name']
        user_id = request.form['user_id']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if the book is available
            cursor.execute("SELECT * FROM books_collection WHERE book_name = %s", (book_name,))
            book = cursor.fetchone()  # Consumes the result

            if not book:
                flash("Book not found in the collection.", "danger")
            elif book[4] == 0:  # Check available_copies column
                flash("No copies available currently.", "warning")
            else:
                issue_date = datetime.now()
                due_date = issue_date + timedelta(days=14)

                # Insert the issued book into the issued_books table
                cursor.execute(
                    "INSERT INTO issued_books (book_id, book_name, user_id, issue_date, due_date) VALUES (%s, %s, %s, %s, %s)",
                    (book[0], book_name, user_id, issue_date, due_date)
                )

                # Update available copies in the books_collection table
                cursor.execute(
                    "UPDATE books_collection SET available_copies = available_copies - 1 WHERE book_id = %s", 
                    (book[0],)
                )

                flash(f"Book '{book_name}' issued successfully! Due date: {due_date.strftime('%Y-%m-%d')}.", "success")

            conn.commit()  # Commit changes to the database
        except Exception as e:
            conn.rollback()  # Rollback in case of error
            flash(f"An error occurred: {e}", "danger")
        finally:
            conn.close()   # Close the connection

        return redirect(url_for('home'))  # Redirect to home page after issuing the book

    return render_template('frontend/issue_book.html')



# Return Book
@app.route('/return_book', methods=['GET', 'POST'])
def return_book():
    if request.method == 'POST':
        book_name = request.form['book_name']
        user_id = request.form['user_id']
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if the book was issued to the user
            cursor.execute(
                "SELECT * FROM issued_books WHERE book_name = %s AND user_id = %s AND date IS NULL", 
                (book_name, user_id)
            )
            issued_book = cursor.fetchone()

            if not issued_book:
                flash("This book is not issued to you.", "danger")
                return redirect(url_for('return_book'))  # Redirect to the same page to close the message

            # If the book is found, proceed with the return logic
            due_date = issued_book[4]  # This should be a datetime object
            days_overdue = (date.date() - due_date.date()).days
            fine = max(0, days_overdue * 10)  # Fine: ₹10 per day overdue

            # Update issued_books and books_collection tables
            cursor.execute(
                "UPDATE issued_books SET date = %s, fine = %s WHERE issue_id = %s", 
                (date, fine, issued_book[0])
            )
            cursor.execute(
                "UPDATE books_collection SET available_copies = available_copies + 1 WHERE book_id = %s", 
                (issued_book[1],)
            )
            conn.commit()

            flash(f"Book returned successfully! Fine: ₹{fine}.", "success")

        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            flash("An error occurred while returning the book.", "danger")
        finally:
            conn.close()

        return redirect(url_for('home'))

    return render_template('frontend/return_book.html')


@app.route('/search_book', methods=['GET'])
def search_book():
    query = request.args.get('query', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    if query:
        cursor.execute("""
            SELECT book_name, author_name, subject, available_copies 
            FROM books_collection 
            WHERE book_name LIKE %s OR author_name LIKE %s OR subject LIKE %s
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    else:
        cursor.execute("SELECT book_name, author_name, subject, available_copies FROM books_collection")

    books = cursor.fetchall()
    conn.close()

    return render_template('frontend/search_book.html', books=books)


# Start the Flask Application
print("Starting Flask application...")
if __name__ == "__main__":
    app.run(debug=True)


