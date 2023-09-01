from flask import *
from flask_sqlalchemy import SQLAlchemy
import requests, io, sqlite3, random, string, os, datetime, urllib3 

urllib3.disable_warnings()


_API_VERSION_ ="v1"

app = Flask(__name__)
app.secret_key = "WolfiexD#0987654321"
MAX_CONTENT_LENGTH = 1024 * 1024 * 50
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fileshare.db'
db = SQLAlchemy(app)

TELEGRAM_BOT_TOKEN = '6657829651:AAHn53qo8pE-c7EegCbOhu0GGHF9jVM6E6s'
TELEGRAM_CHAT_ID = "-1001884906837"
TELEGRAM_CHAT_ID_BACKUP = "-1001956982197"
DATABASE_UPLOAD_CHANNEL = "-1001846223128"
ERROR_LOG_CHANNEL = "-1001941879489"

@app.errorhandler(413)
def request_entity_too_large(e):
    return render_template("fshareindex.html", error_message="File size cannot exceed 50MB."), 413
    
def ErrorReport(error):
    try:
        message = f"**ERROR**\nMessage: `{str(error)}\nTime: `{str(datetime.datetime.now())}`"
        data = {
           'chat_id': ERROR_LOG_CHANNEL,
           'text': message,
           'parse_mode': 'Markdown'
        }
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        response = requests.post(url, data=data, verify=False)
        if response.status_code == 200:
            return True
        else:
            return response.status_code
    except Exception as e:
        print(e)
        return str(e)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filesize = db.Column(db.Integer, nullable=False)
    telegram_file_id = db.Column(db.String(255), nullable=False)
    alias = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.datetime.now)
    mime_type = db.Column(db.String(255), default="application/octet-stream")
    description = db.Column(db.Text, default=None)

def saveFile(filename, filesize, alias, telegram_file_id, mime_type="application/octet-stream", description=None):
    with current_app.app_context():
        new_file = File(filename=filename, filesize=filesize, telegram_file_id=telegram_file_id,
        alias=alias, mime_type=mime_type, description=description)
        db.session.add(new_file)
        db.session.commit()

def getFileInfo(alias):
    with current_app.app_context():
        file_data = File.query.filter_by(alias=alias).first()
        if file_data:
            return {
                'file_name': file_data.filename,
                'file_size': file_data.filesize,
                'telegram_file_id': file_data.telegram_file_id,
                'mime_type': file_data.mime_type,
                'upload_date': file_data.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'description': file_data.description,
            }
        else:
            return None


def generate_alias(ln=8):
    return''.join(random.choice(string.ascii_letters + string.digits) for _ in range(ln))


@app.route('/')
def index(e=None):
    
    if e == 500:
        return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!")
    return render_template("fshareindex.html")
    
@app.route("/500")
def internal_server_error():
    return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!")

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        description = request.form.get("description")
        alias = request.form.get("alias")
        
        if not description:
            description = None
        if not alias:
            alias = generate_alias()
        if getFileInfo(alias):
            #return render_template("fshareindex.html", error_message="Alias already exists. Try using a different one or leave blank.")
            flash("Alias already exists. Try using a different one or leave blank.")
            return redirect(url_for("index"))
        def generate_chunks(stream, chunk_size):
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        file = request.files.get("file")

        if not file:
            #return render_template("fshareindex.html", error_message="No file received.")
            flash("No file received.")
            return redirect(url_for("index"))
        if file.content_length > MAX_CONTENT_LENGTH:
            #return render_template("fshareindex.html", error_message="File size cannot exceed 50MB.")
            flash("File size cannot exceed 50MB.")
            return redirect(url_for("index"))
            
        if file:
            chunk_size = 1024 * 1024  # Adjust the chunk size as needed
            resp = saveToTelegram(file.filename, generate_chunks(file.stream, chunk_size))
            if resp:
                saveFile(filename=resp["file_name"], filesize=resp["file_size"],
                     alias=alias, telegram_file_id=resp["telegram_file_id"], 
                     mime_type=resp["mime_type"], description=description)
                return redirect(request.host_url+alias)
                #return render_template("fshareindex.html", alias=alias)
            else:
                #return render_template("fshareindex.html", error_message="Internal Server Error.")
                flash("Internal Server Error.")
                return redirect(url_for("index"))
                
        #return render_template("fshareindex.html", error_message="No file received.")
        flash("No file received.")
        return redirect(url_for("index"))
    
    except Exception as e:
        if "Request Entity Too Large" in str(e):
            #return render_template("fshareindex.html", error_message="File size cannot exceed 50MB.")
            flash("File size cannot exceed 50MB.")
            return redirect(url_for("index"))
        ErrorReport(str(e))
        print(e)
       # return render_template("fshare500.html"), 500
        return redirect(url_for("internal_server_error"))



def saveToTelegram(filename, chunks):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
    }

    chunks_io = io.BytesIO(b''.join(chunks))

    files = {
        'document': (filename, chunks_io),
    }
    
    response = requests.post(url, data=data, files=files, verify=False)
    print(response.text, response.status_code)
    if response.status_code == 200:
        result = response.json()['result']
        
        # Extract relevant information based on the type of file
        if 'document' in result:
            file_info = result['document']
        elif 'audio' in result:
            file_info = result['audio']
        elif 'photo' in result:
            file_info = result['photo'][0]  # Extract info from the first available photo
        elif 'video' in result:
            file_info = result['video']
        # Add more conditions for other types if needed
        
        file_name = file_info['file_name']
        telegram_file_id = file_info['file_id']
        file_size = file_info['file_size']
        mime_type = file_info.get('mime_type', 'application/octet-stream')
        
        return {
            "file_name": file_name,
            "file_size": file_size,
            "telegram_file_id": telegram_file_id,
            "mime_type": mime_type,
        }
    else:
        return None



@app.route("/<alias>")
def file_info_page(alias):
    try:
        f_info = getFileInfo(alias)
        if not f_info:
            return render_template("fshareerror.html", error_code="404", error_heading="Not Found", error_msg="Page not found!"), 404
    
        file_name=f_info["file_name"]
        file_size=f_info["file_size"]
        telegram_file_id=f_info["telegram_file_id"]
        mime_type=f_info["mime_type"]
        upload_date=f_info["upload_date"]
   
        description=f_info["description"]
   
        #return f"File Name: {file_name}\nFile Size: {str(file_size/1024)}\nMine Type: {mime_type}\nUpload Date: {upload_date}\nDescription: {description}"
        return render_template("fshareinfo.html", alias=alias, file_name=file_name, file_size=file_size, mime_type=mime_type, description=description, upload_date=upload_date)
    except Exception as e:
        ErrorReport(str(e))
        print(e)
        return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!")



@app.route('/<alias>/download')
def dl_file(alias):
    try:
        f_info = getFileInfo(alias)
        if not f_info:
            return render_template("fshareerror.html", error_code="404", error_heading="Not Found", error_msg="Page not found!"), 404
        telegram_file_id = f_info["telegram_file_id"]
        mime_type = f_info["mime_type"]
        file_name = f_info["file_name"]
        def generate_chunks(url, chunk_size):
             with requests.get(url, stream=True) as response:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        yield chunk
    
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
        params = {
             'file_id': telegram_file_id,
         }
        response = requests.get(url, params=params, verify=False)
        if response.status_code == 200:
            file_path = response.json()['result']['file_path']
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        
            # Determine the appropriate chunk size based on your needs
            chunk_size = 1024 * 1024  # 1 MB
        
            headers = {
                'Content-Disposition': f'attachment; filename={file_name}',  # Change the filename extension
                 'Content-Type': mime_type,
            }
        
            return Response(generate_chunks(file_url, chunk_size), headers=headers)
    
        return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!"), 500 
    except Exception as e:
        ErrorReport(str(e))
        print(e)
        return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!"), 500



@app.errorhandler(404)
def page_not_found(e):
    return render_template("fshareerror.html", error_code="404", error_heading="Not Found", error_msg="Page not found!"), 404
    
@app.errorhandler(500)
def internal_server_error_exception(e):
    ErrorReport(str(e))
    print(e)
    return render_template("fshareerror.html", error_code="500", error_heading="Internal Server Error", error_msg="Something went wrong!"), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, threaded=True, host="0.0.0.0")
