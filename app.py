import os
import math
import json
import random
import string
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from whitenoise import WhiteNoise
from flask_mail import Mail, Message

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)

# --- CONFIGURAÇÃO DO E-MAIL (PEGANDO DO RENDER) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

# --- WHITE NOISE (CSS) ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.wsgi_app = WhiteNoise(app.wsgi_app, root=os.path.join(basedir, 'static'), prefix='/static/')


app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-padrao-desenvolvimento')

# --- BANCO DE DADOS ---
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'loja.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS ---

class User(db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False) 
    password_hash = Column(String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# MANTIVE OS MODELOS ORIGINAIS ABAIXO
class Cliente(db.Model):
    __tablename__ = 'Clientes'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    endereco = Column(String(200), nullable=False)
    loja = Column(String(100), nullable=True)
    telefone = Column(String(20), nullable=False)
    estado_uf = Column(String(2), nullable=False)
    tipo_cliente = Column(String(100), nullable=False)
    pedidos = relationship('Pedido', back_populates='cliente')

class Produto(db.Model):
    __tablename__ = 'Produtos'
    id = Column(Integer, primary_key=True)
    nome_produto = Column(String(100), nullable=False)
    preco_varejo = Column(Float, nullable=False)
    preco_atacado = Column(Float, nullable=False)
    preco_atacarejo = Column(Float, nullable=False)
    preco_atacado_premium = Column(Float, nullable=False)
    custo_producao =  Column(Float, nullable=False)
    tempo_producao = Column(Float, nullable=False)

class Pedido(db.Model):
    __tablename__ = 'Pedidos'
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey('Clientes.id'), nullable=False)
    data_pedido = Column(DateTime, default=func.now())
    prazo_entrega = Column(Date, nullable=True)
    status = Column(String(50), default='Pendente')
    forma_envio = Column(String(50), nullable=False)
    desconto = Column(Float, default=0.0)
    cliente = relationship('Cliente', back_populates='pedidos')
    itens = relationship('ItemPedido', back_populates='pedido', cascade="all, delete-orphan")
    pagamentos = relationship('Pagamento', back_populates='pedido', cascade="all, delete-orphan")
    custos_envios = relationship('CustoEnvio', back_populates='pedido', cascade="all, delete-orphan")

class ItemPedido(db.Model):
    __tablename__ = 'Itens_Pedido'
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey('Pedidos.id'), nullable=False)
    produto_id = Column(Integer, ForeignKey('Produtos.id'), nullable=False)
    quantidade = Column(Integer, nullable=False)
    preco_unitario_na_venda = Column(Float, nullable=False)
    custo_unitario_na_venda = Column(Float, nullable=False)
    cor = Column(String(50), nullable=True)
    pedido = relationship('Pedido', back_populates='itens')
    produto = relationship('Produto')

class Pagamento(db.Model):
    __tablename__ = 'Pagamentos'
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey('Pedidos.id'), nullable=False)
    metodo = Column(String(50), nullable=False)
    valor = Column(Float, nullable=False)
    pedido = relationship('Pedido', back_populates='pagamentos')

class CustoEnvio(db.Model):
    __tablename__ = 'Custos_Envio'
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey('Pedidos.id'), nullable=False)
    tipo_custo = Column(String(50), nullable=False)
    valor = Column(Float, nullable=False)
    status = Column(String(20), default='Pendente')
    pedido = relationship('Pedido', back_populates='custos_envios')

# --- ROTAS DE CONFIGURAÇÃO E LOGIN ---

@app.route('/')
def index():
    # Verifica se já existe algum usuário no banco
    try:
        if User.query.count() == 0:
            return redirect(url_for('setup_mestre'))
    except:
        # Se der erro (tabela não existe), tenta criar
        db.create_all()
        return redirect(url_for('setup_mestre'))
    
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup_mestre():
    # Segurança: Se já existe usuário, bloqueia essa tela
    if User.query.count() > 0:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        user = User(username=request.form['username'], email=request.form['email'])
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        flash('Usuário Mestre Configurado! O sistema está pronto.', 'success')
        return redirect(url_for('login'))
    
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Bem-vindo ao sistema!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Dados incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

# --- RECUPERAÇÃO DE SENHA

@app.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email_digitado = request.form['email']
        user = User.query.filter_by(email=email_digitado).first()
        
        if user:
            codigo = ''.join(random.choices(string.digits, k=6))
            session['reset_code'] = codigo
            session['reset_email'] = email_digitado
            
            try:
                # Usa as variáveis do Render que configuramos (image_d0cb8e.png)
                msg = Message('Recuperação de Senha - Ateliê Vanda',
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[email_digitado])
                msg.body = f'Seu código de verificação é: {codigo}'
                mail.send(msg)
                flash(f'Código enviado para {email_digitado}!', 'info')
                return redirect(url_for('validar_codigo'))
            except Exception as e:
                flash(f'Erro no envio: {str(e)}', 'danger')
        else:
            flash('E-mail não encontrado.', 'warning')
            
    return render_template('esqueci_senha.html')

@app.route('/validar-codigo', methods=['GET', 'POST'])
def validar_codigo():
    if 'reset_code' not in session: return redirect(url_for('esqueci_senha'))
    if request.method == 'POST':
        if request.form['codigo'] == session['reset_code']:
            return redirect(url_for('nova_senha'))
        flash('Código inválido.', 'danger')
    return render_template('validar_codigo.html')

@app.route('/nova-senha', methods=['GET', 'POST'])
def nova_senha():
    if 'reset_email' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user = User.query.filter_by(email=session['reset_email']).first()
        if user:
            user.set_password(request.form['password'])
            db.session.commit()
            session.pop('reset_code', None)
            session.pop('reset_email', None)
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('login'))
    return render_template('nova_senha.html')

@app.route('/home')
def home():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/acompanhar_pedidos', methods=['GET', 'POST'])
def acompanhar_pedidos():
    # Rota PÚBLICA (Login não é necessário)
    pedidos = []
    cliente_encontrado = None
    
    if request.method == 'POST':
        termo = request.form.get('cliente_id')
        
        # Tenta buscar pelo ID (se for número)
        if termo and termo.isdigit():
            cliente_encontrado = Cliente.query.get(int(termo))
            
            if cliente_encontrado:
                # Busca os pedidos desse cliente, do mais recente para o mais antigo
                pedidos = Pedido.query.filter_by(cliente_id=cliente_encontrado.id).order_by(Pedido.id.desc()).all()
                if not pedidos:
                    flash('Você ainda não possui pedidos registrados.', 'info')
            else:
                flash('Cliente não encontrado com este ID.', 'danger')
        else:
            flash('Por favor, digite um ID válido (apenas números).', 'warning')

    return render_template('acompanhar_pedido.html', pedidos=pedidos, cliente=cliente_encontrado)

@app.route('/emergencia-criar-mestre')
def emergencia():
    try:
        # Verifica se já existe
        if User.query.count() > 0:
            return "Já existe usuário cadastrado!"
        
        # Cria o usuário mestre na força
        u = User(username="admin", email="seu-email@gmail.com") # <--- Coloque seu e-mail aqui
        u.set_password("123456") # <--- Senha provisória
        db.session.add(u)
        db.session.commit()
        return "Usuário Mestre recriado! Login: admin | Senha: 123456"
    except Exception as e:
        return f"Erro: {e}"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)