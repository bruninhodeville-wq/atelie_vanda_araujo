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

# --- CONFIGURAÇÃO DO E-MAIL (Variáveis de Ambiente do Render) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

# --- WHITE NOISE (Arquivos Estáticos/CSS) ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.wsgi_app = WhiteNoise(app.wsgi_app, root=os.path.join(basedir, 'static'), prefix='/static/')

# Chave secreta segura
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-padrao-desenvolvimento')

# --- BANCO DE DADOS (PostgreSQL) ---
database_url = os.environ.get('DATABASE_URL')

# Verifica se existe uma URL configurada no Render
if database_url:
    # Correção para o Render: Se vier como "postgres://", muda para "postgresql://"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Define o banco como PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Se não tiver URL configurada, usa SQLite (apenas para teste local no PC)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'loja.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS (TABELAS) ---

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


# --- ROTAS DE ACESSO E AUTENTICAÇÃO ---

@app.route('/')
def index():
    # Rota padrão: Se logado vai pra Home, senão vai pra Login
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# --- RECUPERAÇÃO DE SENHA (ESQUECI MINHA SENHA) ---

@app.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email_digitado = request.form['email']
        user = User.query.filter_by(email=email_digitado).first()
        
        if user:
            # Gera código aleatório de 6 dígitos
            codigo = ''.join(random.choices(string.digits, k=6))
            session['reset_code'] = codigo
            session['reset_email'] = email_digitado
            
            try:
                msg = Message('Recuperação de Senha - Ateliê Vanda',
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[email_digitado])
                msg.body = f'Seu código de recuperação é: {codigo}'
                mail.send(msg)
                flash(f'Código enviado para {email_digitado}!', 'info')
                return redirect(url_for('validar_codigo'))
            except Exception as e:
                flash(f'Erro ao enviar e-mail (Verifique config do Render): {str(e)}', 'danger')
        else:
            flash('E-mail não encontrado no sistema.', 'warning')
            
    return render_template('esqueci_senha.html')

@app.route('/validar-codigo', methods=['GET', 'POST'])
def validar_codigo():
    if 'reset_code' not in session: return redirect(url_for('esqueci_senha'))
    
    if request.method == 'POST':
        if request.form['codigo'] == session['reset_code']:
            return redirect(url_for('nova_senha'))
        flash('Código incorreto.', 'danger')
        
    return render_template('validar_codigo.html')

@app.route('/nova-senha', methods=['GET', 'POST'])
def nova_senha():
    if 'reset_email' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=session['reset_email']).first()
        if user:
            user.set_password(request.form['password'])
            db.session.commit()
            
            # Limpa sessão
            session.pop('reset_code', None)
            session.pop('reset_email', None)
            
            flash('Senha alterada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
            
    return render_template('nova_senha.html')


# --- ÁREA PÚBLICA (RASTREIO) ---

@app.route('/acompanhar_pedidos', methods=['GET', 'POST'])
def acompanhar_pedidos():
    # Rota PÚBLICA (Login não obrigatório)
    pedidos = []
    cliente_encontrado = None
    
    if request.method == 'POST':
        termo = request.form.get('cliente_id')
        
        if termo and termo.isdigit():
            cliente_encontrado = Cliente.query.get(int(termo))
            if cliente_encontrado:
                pedidos = Pedido.query.filter_by(cliente_id=cliente_encontrado.id).order_by(Pedido.id.desc()).all()
                if not pedidos:
                    flash('Você ainda não possui pedidos registrados.', 'info')
            else:
                flash('Cliente não encontrado com este ID.', 'danger')
        else:
            flash('Por favor, digite um ID válido (apenas números).', 'warning')

    return render_template('acompanhar_pedido.html', pedidos=pedidos, cliente=cliente_encontrado)


# --- ROTAS ADMINISTRATIVAS (LOGIN OBRIGATÓRIO) ---

@app.route('/home')
def home():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    total_pedidos = Pedido.query.count()
    total_clientes = Cliente.query.count()
    total_produtos = Produto.query.count()
    return render_template('dashboard.html', qtd_pedidos=total_pedidos, qtd_clientes=total_clientes, qtd_produtos=total_produtos)

# --- CLIENTES ---
@app.route('/clientes', methods=['GET'])
def clientes():
    if 'user_id' not in session: return redirect(url_for('login'))
    clientes_cadastrados = Cliente.query.order_by(Cliente.nome).all()
    return render_template('clientes.html', lista_de_clientes=clientes_cadastrados)

@app.route('/clientes/novo', methods=['GET', 'POST'])
def novo_cliente():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        email_digitado = request.form['email']
        if email_digitado == "": email_digitado = None
        novo = Cliente(
            nome=request.form['nome'],
            telefone=request.form['telefone'],
            email=email_digitado,
            endereco=request.form['endereco'],
            estado_uf=request.form['estado_uf'],
            loja=request.form['loja'],
            tipo_cliente=request.form['tipo_cliente']
        )
        try:
            db.session.add(novo)
            db.session.commit()
            flash('Cliente cadastrado com sucesso!', 'success')
            return redirect(url_for('clientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar: {e}', 'danger')
    return render_template('novo_cliente.html')

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.telefone = request.form['telefone']
        cliente.email = request.form['email']
        cliente.endereco = request.form['endereco']
        cliente.estado_uf = request.form['estado_uf']
        cliente.loja = request.form['loja']
        cliente.tipo_cliente = request.form['tipo_cliente']
        try:
            db.session.commit()
            flash('Cliente atualizado!', 'success')
            return redirect(url_for('clientes'))
        except:
            db.session.rollback()
            flash('Erro ao atualizar.', 'danger')
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/clientes/deletar/<int:id>', methods=['GET', 'POST'])
def deletar_cliente(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        senha = request.form['password']
        user = User.query.get(session['user_id'])
        if user and user.check_password(senha):
            try:
                db.session.delete(cliente)
                db.session.commit()
                flash('Cliente deletado.', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro: {e}', 'danger')
        else:
            flash('Senha incorreta.', 'danger')
    return render_template('confirmar_delete.html', cliente=cliente)

# --- PRODUTOS ---
@app.route('/produtos', methods=['GET'])
def produtos():
    if 'user_id' not in session: return redirect(url_for('login'))
    produtos_cadastrados = Produto.query.order_by(Produto.nome_produto).all()
    return render_template('produtos.html', lista_de_produtos=produtos_cadastrados)

@app.route('/produtos/novo', methods=['GET', 'POST'])
def novo_produto():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            novo = Produto(
                nome_produto=request.form['nome_produto'],
                preco_varejo=float(request.form['preco_varejo']),
                preco_atacado=float(request.form['preco_atacado']),
                preco_atacarejo=float(request.form['preco_atacarejo']),
                preco_atacado_premium=float(request.form['preco_atacado_premium']),
                custo_producao=float(request.form['custo_producao']),
                tempo_producao=float(request.form['tempo_producao'])
            )
            db.session.add(novo)
            db.session.commit()
            flash('Produto criado!', 'success')
            return redirect(url_for('produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('novo_produto.html')

@app.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        try:
            produto.nome_produto = request.form['nome_produto']
            produto.preco_varejo = float(request.form['preco_varejo'])
            produto.preco_atacado = float(request.form['preco_atacado'])
            produto.preco_atacarejo = float(request.form['preco_atacarejo'])
            produto.preco_atacado_premium = float(request.form['preco_atacado_premium'])
            produto.custo_producao = float(request.form['custo_producao'])
            produto.tempo_producao = float(request.form['tempo_producao'])
            db.session.commit()
            flash('Produto atualizado!', 'success')
            return redirect(url_for('produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('editar_produto.html', produto=produto)

@app.route('/produtos/deletar/<int:id>', methods=['GET', 'POST'])
def deletar_produto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        senha = request.form['password']
        user = User.query.get(session['user_id'])
        if user and user.check_password(senha):
            try:
                db.session.delete(produto)
                db.session.commit()
                flash('Produto deletado.', 'success')
                return redirect(url_for('produtos'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro: {e}', 'danger')
        else:
            flash('Senha incorreta.', 'danger')
    return render_template('confirmar_delete_produto.html', produto=produto)

# --- PEDIDOS ---
@app.route('/pedidos')
def pedidos():
    if 'user_id' not in session: return redirect(url_for('login'))
    pedidos_cadastrados = Pedido.query.order_by(Pedido.id.desc()).all()
    return render_template('pedidos.html', lista_de_pedidos=pedidos_cadastrados)

@app.route('/pedidos/novo', methods=['GET', 'POST'])
def novo_pedido():
    if 'user_id' not in session: return redirect(url_for('login'))

    editar_id = request.args.get('editar_id')
    pedido_atual = None
    itens_existentes_json = '[]'

    if editar_id:
        pedido_atual = Pedido.query.get(editar_id)
        if pedido_atual:
            lista_temp = []
            for item in pedido_atual.itens:
                lista_temp.append({
                    'id': str(item.produto_id),
                    'nome': item.produto.nome_produto,
                    'cor': item.cor,
                    'qty': item.quantidade,
                    'preco': item.preco_unitario_na_venda,
                    'tabela': 'Recuperado', # Simples indicador visual
                    'subtotal': item.preco_unitario_na_venda * item.quantidade
                })
            itens_existentes_json = json.dumps(lista_temp)

    if request.method == 'POST':
        try:
            pedido_id_form = request.form.get('pedido_id_editar')
            cliente_id = int(request.form['cliente_id'])
            forma_envio = request.form['forma_envio']
            itens_json = request.form['itens_carrinho']
            lista_de_itens = json.loads(itens_json)

            if not lista_de_itens:
                flash('O carrinho está vazio!', 'warning')
                return redirect(url_for('novo_pedido'))

            tempo_total_horas = 0
            for item in lista_de_itens:
                prod = Produto.query.get(int(item['id']))
                tempo_total_horas += prod.tempo_producao * int(item['qty'])
            
            dias_producao = math.ceil(tempo_total_horas / 10)
            data_prazo = datetime.now() + timedelta(days=dias_producao)

            if pedido_id_form:
                pedido_salvo = Pedido.query.get(pedido_id_form)
                pedido_salvo.cliente_id = cliente_id
                pedido_salvo.forma_envio = forma_envio
                pedido_salvo.prazo_entrega = data_prazo
                # Remove itens antigos para recriar com base no carrinho novo
                for item_velho in pedido_salvo.itens:
                    db.session.delete(item_velho)
            else:
                pedido_salvo = Pedido(
                    cliente_id=cliente_id,
                    forma_envio=forma_envio,
                    data_pedido=datetime.now(),
                    prazo_entrega=data_prazo,
                    status="Rascunho",
                    desconto=0.0
                )
                db.session.add(pedido_salvo)

            for item in lista_de_itens:
                produto_db = Produto.query.get(int(item['id']))
                preco_unitario = float(item['preco']) 
                
                novo_item_db = ItemPedido(
                    pedido=pedido_salvo if not pedido_id_form else None,
                    pedido_id=pedido_salvo.id if pedido_id_form else None,
                    produto_id=produto_db.id,
                    quantidade=int(item['qty']),
                    preco_unitario_na_venda=preco_unitario,
                    custo_unitario_na_venda=produto_db.custo_producao,
                    cor=item['cor']
                )
                db.session.add(novo_item_db)

            db.session.commit()
            return redirect(url_for('tela_pagamento', id=pedido_salvo.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar: {e}', 'danger')

    clientes = Cliente.query.order_by(Cliente.nome).all()
    produtos = Produto.query.order_by(Produto.nome_produto).all()
    
    proximo_id_tela = "Novo"
    if pedido_atual:
        proximo_id_tela = pedido_atual.id
    
    return render_template('novo_pedido.html', 
                           clientes=clientes, 
                           produtos=produtos, 
                           proximo_id=proximo_id_tela,
                           pedido_atual=pedido_atual,
                           itens_pre_carregados=itens_existentes_json)

@app.route('/pedidos/pagamento/<int:id>', methods=['GET'])
def tela_pagamento(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pedido = Pedido.query.get_or_404(id)
    total_valor = 0
    total_horas = 0
    for item in pedido.itens:
        total_valor += item.preco_unitario_na_venda * item.quantidade
        prod = Produto.query.get(item.produto_id)
        total_horas += prod.tempo_producao * item.quantidade
    dias = math.ceil(total_horas / 10)
    return render_template('pagamento_pedido.html', pedido=pedido, total_valor=total_valor, total_horas=total_horas, dias_producao=dias)

@app.route('/pedidos/salvar_pagamento/<int:id>', methods=['POST'])
def salvar_pagamento(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pedido = Pedido.query.get_or_404(id)
    try:
        pedido.desconto = float(request.form['valor_desconto_final'])
        
        data_texto = request.form['prazo_entrega']
        pedido.prazo_entrega = datetime.strptime(data_texto, '%Y-%m-%d').date()

        v_sinal = float(request.form['valor_pago']) if request.form['valor_pago'] else 0.0
        if v_sinal > 0:
            pgto = Pagamento(pedido_id=pedido.id, metodo=request.form['metodo_pagamento'], valor=v_sinal)
            db.session.add(pgto)

        taxas = request.form['lista_taxas_json']
        if taxas:
            lista = json.loads(taxas)
            for t in lista:
                nc = CustoEnvio(pedido_id=pedido.id, tipo_custo=t['tipo'], valor=float(t['valor']), status=t['status'])
                db.session.add(nc)
                if t['status'] == 'Pago':
                    pgto_t = Pagamento(pedido_id=pedido.id, metodo="Taxa/Outro", valor=float(t['valor']))
                    db.session.add(pgto_t)
        
        pedido.status = "Pendente" 
        db.session.commit()
        flash(f'Pedido #{pedido.id} finalizado!', 'success')
        return redirect(url_for('pedidos'))
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
        return redirect(url_for('tela_pagamento', id=id))

@app.route('/pedidos/detalhes/<int:id>')
def detalhes_pedido(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pedido = Pedido.query.get_or_404(id)
    total_prod = sum(item.preco_unitario_na_venda * item.quantidade for item in pedido.itens)
    desc = pedido.desconto if pedido.desconto else 0.0
    liq = total_prod - desc
    taxas = sum(c.valor for c in pedido.custos_envios)
    geral = liq + taxas
    pago = sum(p.valor for p in pedido.pagamentos)
    pend = geral - pago
    return render_template('detalhes_pedido.html', pedido=pedido, total_produtos=total_prod, valor_desconto=desc, total_produtos_liquido=liq, total_taxas=taxas, total_geral=geral, total_pago=pago, valor_pendente=pend)

@app.route('/pedidos/editar/<int:id>', methods=['GET', 'POST'])
def editar_pedido(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pedido = Pedido.query.get_or_404(id)
    if request.method == 'POST':
        try:
            pedido.status = request.form['status']
            pedido.forma_envio = request.form['forma_envio']
            pedido.prazo_entrega = datetime.strptime(request.form['prazo_entrega'], '%Y-%m-%d').date()
            db.session.commit()
            flash('Pedido atualizado!', 'success')
            return redirect(url_for('pedidos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('editar_pedido.html', pedido=pedido)

@app.route('/pedidos/deletar/<int:id>', methods=['GET', 'POST'])
def deletar_pedido(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pedido = Pedido.query.get_or_404(id)
    if request.method == 'POST':
        senha = request.form['password']
        user = User.query.get(session['user_id'])
        if user and user.check_password(senha):
            try:
                db.session.delete(pedido)
                db.session.commit()
                flash('Pedido excluído.', 'success')
                return redirect(url_for('pedidos'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro: {e}', 'danger')
        else:
            flash('Senha incorreta.', 'danger')
    return render_template('confirmar_delete_pedido.html', pedido=pedido)

# --- DEBUG & EXECUÇÃO ---

@app.route('/debug')
def debug():
    # Rota simples para verificar pastas no servidor se precisar
    import os
    try:
        conteudo = os.listdir(os.path.join(basedir, 'static', 'css'))
        return f"CSS Encontrado: {conteudo}"
    except Exception as e:
        return f"Erro ao ler estáticos: {e}"
    
# --- ROTA DE CORREÇÃO (USAR UMA VEZ PARA CRIAR AS TABELAS NO POSTGRES) ---
@app.route('/fix-banco')
def fix_banco():
    try:
        # 1. Cria as tabelas que faltam
        db.create_all()
        
        # 2. Verifica se o Mestre já existe
        if User.query.count() == 0:
            # Cria o usuário Mestre
            u = User(username="admin", email="seu-email@gmail.com") # <--- CONFIRA SEU E-MAIL AQUI
            u.set_password("123456") # <--- SENHA PROVISÓRIA
            db.session.add(u)
            db.session.commit()
            return "SUCESSO: Tabelas Criadas e Usuário 'admin' (senha 123456) criado!"
        else:
            return "SUCESSO: Tabelas já existem e usuário também."
            
    except Exception as e:
        return f"ERRO: {str(e)}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)