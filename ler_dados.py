import sqlite3
import os

# Conecta no banco local antigo
if os.path.exists('loja.db'):
    conn = sqlite3.connect('loja.db')
    cursor = conn.cursor()
    
    with open('dados_antigos.txt', 'w', encoding='utf-8') as f:
        f.write("=== RELATÓRIO DE DADOS ANTIGOS (LOCAL) ===\n\n")

        # --- CLIENTES ---
        f.write("--- CLIENTES ---\n")
        try:
            cursor.execute("SELECT id, nome, email, telefone, endereco, tipo_cliente FROM Clientes")
            clientes = cursor.fetchall()
            for c in clientes:
                f.write(f"ID: {c[0]} | Nome: {c[1]} | Tel: {c[3]} | Tipo: {c[5]}\n")
                f.write(f"   Endereço: {c[4]}\n")
                f.write(f"   Email: {c[2]}\n")
                f.write("-" * 30 + "\n")
        except:
            f.write("(Tabela Clientes não encontrada ou vazia)\n")

        f.write("\n\n")

        # --- PRODUTOS ---
        f.write("--- PRODUTOS ---\n")
        try:
            cursor.execute("SELECT id, nome_produto, preco_varejo, preco_atacado, custo_producao, tempo_producao FROM Produtos")
            produtos = cursor.fetchall()
            for p in produtos:
                f.write(f"ID: {p[0]} | Produto: {p[1]}\n")
                f.write(f"   Varejo: R$ {p[2]} | Atacado: R$ {p[3]}\n")
                f.write(f"   Custo: R$ {p[4]} | Tempo: {p[5]}h\n")
                f.write("-" * 30 + "\n")
        except:
             f.write("(Tabela Produtos não encontrada ou vazia)\n")
        
        f.write("\n\n")

        # --- PEDIDOS ---
        f.write("--- PEDIDOS (Recentes Primeiro) ---\n")
        try:
            # Tenta buscar pedidos e seus itens
            cursor.execute("""
                SELECT p.id, c.nome, p.data_pedido, p.status, p.forma_envio, p.desconto 
                FROM Pedidos p 
                JOIN Clientes c ON p.cliente_id = c.id
                ORDER BY p.id DESC
            """)
            pedidos = cursor.fetchall()
            
            for ped in pedidos:
                f.write(f"PEDIDO #{ped[0]} | Cliente: {ped[1]} | Status: {ped[3]}\n")
                f.write(f"   Data: {ped[2]} | Envio: {ped[4]} | Desconto: {ped[5]}\n")
                f.write("   ITENS:\n")
                
                # Busca itens deste pedido
                cursor.execute("""
                    SELECT pr.nome_produto, i.quantidade, i.preco_unitario_na_venda, i.cor 
                    FROM Itens_Pedido i
                    JOIN Produtos pr ON i.produto_id = pr.id
                    WHERE i.pedido_id = ?
                """, (ped[0],))
                itens = cursor.fetchall()
                
                for item in itens:
                    f.write(f"    - {item[1]}x {item[0]} ({item[3]}) | R$ {item[2]}\n")
                
                f.write("=" * 40 + "\n")

        except Exception as e:
            f.write(f"(Erro ao ler pedidos: {e})\n")

    conn.close()
    print("Sucesso! Abra o arquivo 'dados_antigos.txt' para ver suas informações.")
else:
    print("Erro: Arquivo 'loja.db' não encontrado nesta pasta.")