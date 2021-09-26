import time
from flask import current_app, Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from flask_mail import Message
from . import db, mail, serializer

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    logout_user()
    return render_template('login.html')

@auth.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.query.filter_by(email=email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash('Mot de passe incorrect')
        return redirect(url_for('auth.login'))

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)
    return redirect(url_for('main.profile'))

@auth.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@auth.route('/change_password', methods=['POST'])
def change_password():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify([False, "Cet user n'a pas de compte"])

    data = {"i":str(user.id), "s": user.seqid, "t": int(time.time()/3600)}
    token = serializer.dumps(data)

    msg = Message( 
                'Mot de passe oublié', 
                sender ='app@repaircafe-orsay.org', 
                recipients = [email]
    ) 
    msg.body = '''Hello, 

Vous recevez cet email car quelqu'un a demandé une réinitalisation de votre password
sur %s. Si c'est bien vous, pour réinitialiser votre mot de passe, 
rendez-vous sur cette url: %s%s''' % (current_app.config["APP_URL"], current_app.config["APP_URL"], url_for('auth.init_password', token=token))
    mail.send(msg)

    return jsonify([True, "Vérifiez vos emails"])


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/init_password/<string:token>', methods=['GET'])
def init_password(token):
    logout_user()

    data = serializer.loads(token)
    user = User.query.filter_by(id=data["i"]).first()

    if user.seqid != data["s"] or int(time.time()/3600)-data["t"] >= 1:
        flash('Le lien pour changer le password n\'est plus valide')
        return redirect(url_for('auth.login'))

    user.seqid = user.seqid+1
    db.session.commit()

    return render_template('new_password.html', email=user.email, token=serializer.dumps({"i":str(user.id), "s": user.seqid}))

@auth.route('/init_password', methods=['POST'])
def post_new_password():
    logout_user()

    data = serializer.loads(request.form.get('token'))
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(id=data["i"]).first()

    if user.seqid != data["s"]:
        flash('Le lien pour changer le password n\'est plus valide')
        return redirect(url_for('auth.login'))

    user.seqid = user.seqid+1
    user.password = generate_password_hash(password, method='sha256')
    db.session.commit()

    return render_template('login.html')
 