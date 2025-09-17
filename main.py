# main.py
import customtkinter as ctk
from gui import BlockchainApp
from blockchain import Blockchain
from wallet import Wallet
import json
import threading
from flask import Flask, jsonify, request
import sys
import os
import hashlib
import uuid
import requests
import time
from datetime import datetime

# --- Gerenciador de Usuários ---
class UserManager:
    def __init__(self, filename="users.json"):
        self.users_dir = "data/users"
        os.makedirs(self.users_dir, exist_ok=True)
        self.filename = os.path.join(self.users_dir, filename)
        self.users = self.load_users()

    def load_users(self):
        if not os.path.exists(self.filename): return {}
        try:
            with open(self.filename, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {}

    def save_users(self):
        with open(self.filename, 'w') as f: json.dump(self.users, f, indent=4)

    def register(self, username, password):
        if not (username and password): return False, "Usuário e senha não podem estar em branco."
        if username in self.users: return False, "Usuário já existe."
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        wallet = Wallet()
        _, public_key = wallet.create_keys()
        wallet.save_keys(username, password)
        self.users[username] = {"password_hash": password_hash, "public_key": public_key}
        self.save_users()
        return True, "Usuário registrado com sucesso."

    def login(self, username, password):
        user = self.users.get(username)
        if user and user["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
            try:
                wallet = Wallet(username, password)
                return username, wallet
            except ValueError as e:
                print(e)
                return None, None
        return None, None

# --- Aplicação Principal ---
class MainApplication(BlockchainApp):
    def __init__(self, port):
        super().__init__()
        self.withdraw()
        self.user_manager = UserManager()
        self.current_username = None
        self.current_user_wallet = None
        self.port = port
        self.blockchain = None
        self.flask_thread = None
        self.gui_queue = []
        self.after(250, self.process_gui_queue)
        self.show_login_window()

    def initialize_blockchain(self):
        self.blockchain = Blockchain(self.port)
        self.deiconify()
        self.log_event("INICIALIZAÇÃO", f"Bem-vindo, {self.current_username}! Blockchain inicializada.")

        # Conecta botões
        self.main_view_button.configure(command=lambda: self.select_frame("blockchain"))
        self.profile_button.configure(command=lambda: self.select_frame("profile"))
        self.marketplace_button.configure(command=lambda: self.select_frame("marketplace"))
        self.explorer_button.configure(command=lambda: self.select_frame("explorer"))
        self.audit_button.configure(command=lambda: self.select_frame("audit"))
        self.sync_button.configure(command=self.sync_chain)
        self.register_asset_button.configure(command=self.show_register_asset_window)
        self.faucet_button.configure(command=self.request_faucet_funds)
        self.transfer_button.configure(command=self.show_transfer_window)
        self.buy_button.configure(command=self.handle_buy_button_click)
        
        # Conecta eventos de tabelas
        self.blocks_table.bind('<<TreeviewSelect>>', self.on_block_select)
        self.contracts_table.bind('<<TreeviewSelect>>', self.on_contract_select)
        self.all_tokens_table.bind('<<TreeviewSelect>>', self.on_explorer_token_select)
        self.token_table.bind('<ButtonRelease-1>', self.handle_token_action_click)
        
        if self.port == 5001: self.blockchain.add_node('127.0.0.1:5002')
        elif self.port == 5002: self.blockchain.add_node('127.0.0.1:5001')
        
        self.flask_thread = threading.Thread(target=run_flask_app, args=(self.port,), daemon=True)
        self.flask_thread.start()
        
        self.select_frame("profile")
        self.log_event("REDE", "Sincronizando com a rede ao iniciar...")
        self.sync_chain()

    def log_event(self, event_type, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{event_type.ljust(12)}] {message}\n"
        self.gui_queue.append({"type": "log", "message": log_message})

    def process_gui_queue(self):
        update_needed = False
        for item in self.gui_queue:
            if item.get("type") == "log":
                self.audit_log_text.configure(state="normal")
                self.audit_log_text.insert("0.0", item["message"])
                self.audit_log_text.configure(state="disabled")
            elif item.get("type") == "update_display":
                update_needed = True
        if update_needed:
            self.update_all_displays()
        self.gui_queue = []
        self.after(250, self.process_gui_queue)

    def mine_block(self):
        last_block = self.blockchain.last_block
        proof = self.blockchain.proof_of_work(last_block['proof'])
        self.blockchain.add_transaction("0", self.current_user_wallet.public_key, "reward", {'type': 'MINING_REWARD'})
        previous_hash = self.blockchain.hash(last_block)
        new_block = self.blockchain.create_block(proof, previous_hash)
        self.log_event("MINERAÇÃO", f"Novo bloco #{new_block['index']} minerado com sucesso.")
        self.broadcast_new_block(new_block)
        self.update_all_displays()

    def broadcast_new_block(self, block):
        self.log_event("REDE", f"Transmitindo bloco #{block['index']} para {len(self.blockchain.nodes)} nós.")
        for node_address in self.blockchain.nodes:
            try:
                requests.post(f'http://{node_address}/new_block', json=block, timeout=2)
            except requests.exceptions.RequestException:
                self.log_event("ERRO DE REDE", f"Falha ao contatar o nó {node_address}.")

    def sync_chain(self):
        replaced = self.blockchain.resolve_conflicts()
        if replaced:
            self.log_event("CONSENSO", "Cadeia local desatualizada. Substituída pela mais longa da rede.")
        else:
            self.log_event("CONSENSO", "Cadeia local já está sincronizada.")
        self.update_all_displays()

    def show_login_window(self):
        self.login_window = ctk.CTkToplevel(self)
        self.login_window.title("Login / Cadastro")
        self.login_window.geometry("400x400")
        self.login_window.grab_set()
        self.login_window.focus_force()
        ctk.CTkLabel(self.login_window, text="Usuário:").pack(pady=5)
        self.username_entry = ctk.CTkEntry(self.login_window)
        self.username_entry.pack(pady=5)
        ctk.CTkLabel(self.login_window, text="Senha:").pack(pady=5)
        self.password_entry = ctk.CTkEntry(self.login_window, show="*")
        self.password_entry.pack(pady=5)
        self.msg_label = ctk.CTkLabel(self.login_window, text="")
        self.msg_label.pack(pady=10)
        ctk.CTkButton(self.login_window, text="Login", command=self.handle_login).pack(pady=5)
        ctk.CTkButton(self.login_window, text="Registrar", command=self.handle_register).pack(pady=5)
        self.login_window.protocol("WM_DELETE_WINDOW", self.destroy)

    def handle_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        uname, wallet = self.user_manager.login(username, password)
        if wallet:
            self.current_username = uname
            self.current_user_wallet = wallet
            self.login_window.destroy()
            self.initialize_blockchain()
        else:
            self.msg_label.configure(text="Usuário ou senha inválidos.", text_color="red")

    def handle_register(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        success, message = self.user_manager.register(username, password)
        if success:
            self.log_event("USUÁRIO", f"Novo usuário '{username}' registrado localmente.")
        color = "green" if success else "red"
        self.msg_label.configure(text=message, text_color=color)

    def select_frame(self, name):
        frames = {"blockchain": self.blockchain_frame, "profile": self.profile_frame, "marketplace": self.marketplace_frame, "audit": self.audit_frame, "explorer": self.explorer_frame}
        for f in frames.values():
            f.grid_forget()
        frames[name].grid(row=0, column=0, sticky="nsew")
        self.update_all_displays()

    def update_all_displays(self):
        if not self.blockchain: return
        
        # Block Explorer
        for item in self.blocks_table.get_children(): self.blocks_table.delete(item)
        for block in reversed(self.blockchain.chain):
            block_hash = self.blockchain.hash(block)
            self.blocks_table.insert("", "end", values=(block['index'], len(block['transactions']), f"{block_hash[:16]}..."), iid=block['index'])

        # Profile
        address = self.current_user_wallet.public_key
        my_hash = hashlib.sha256(address.encode()).hexdigest()[:16]
        balance = self.blockchain.get_balance(address)
        tokens = self.blockchain.get_owned_tokens(address)
        self.username_label.configure(text=f"Bem-vindo, {self.current_username}!")
        self.address_value.delete("1.0", ctk.END); self.address_value.insert("0.0", address)
        self.my_hash_value.configure(text=my_hash)
        self.balance_value.configure(text=f"Saldo: {balance} Moedas")
        for item in self.token_table.get_children(): self.token_table.delete(item)
        for token in tokens: self.token_table.insert("", "end", values=(token, "Vender"), iid=token)

        # Marketplace
        contracts = self.blockchain.get_contracts()
        for item in self.contracts_table.get_children(): self.contracts_table.delete(item)
        for cid, data in contracts.items():
            seller_hash = hashlib.sha256(data['seller'].encode()).hexdigest()[:16]
            expires_timestamp = data.get('valid_until', 0)
            expires_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(expires_timestamp)) if expires_timestamp > 0 else "N/A"
            status = data['status']
            if time.time() > expires_timestamp and status == 'OPEN':
                status = 'EXPIRADO'
            self.contracts_table.insert("", "end", values=(cid[:8], data['token_id'], data['price'], status, seller_hash, expires_str), iid=cid)
        
        # Asset Explorer
        all_tokens = self.blockchain.state['tokens']
        for item in self.all_tokens_table.get_children(): self.all_tokens_table.delete(item)
        for token_id, owner_address in all_tokens.items():
            owner_hash = hashlib.sha256(owner_address.encode()).hexdigest()[:16]
            self.all_tokens_table.insert("", "end", values=(token_id, owner_hash), iid=token_id)
    
    def on_block_select(self, event):
        selection = self.blocks_table.selection()
        if not selection: return
        block_index = int(selection[0])
        block = self.blockchain.chain[block_index - 1]
        
        details = self.format_block_details(block)
        
        self.block_details_label.configure(text=f"Detalhes do Bloco #{block_index}")
        self.block_details_text.configure(state="normal")
        self.block_details_text.delete("1.0", ctk.END)
        self.block_details_text.insert("0.0", details)
        self.block_details_text.configure(state="disabled")

    def format_block_details(self, block):
        lines = []
        lines.append(f"ÍNDICE.......: {block['index']}")
        lines.append(f"TIMESTAMP....: {datetime.fromtimestamp(block['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Nº TRANSAÇÕES: {len(block['transactions'])}")
        lines.append(f"PROVA (NONCE): {block['proof']}")
        lines.append(f"HASH ANTERIOR: {block['previous_hash']}")
        lines.append(f"HASH ATUAL...: {self.blockchain.hash(block)}")
        lines.append("-" * 60)
        lines.append("TRANSAÇÕES CONTIDAS NO BLOCO:")
        
        for i, tx_data in enumerate(block['transactions']):
            tx = tx_data['transaction']; data = tx['data']; payload = data.get('payload', {})
            sender_hash = "SISTEMA" if tx['sender'] == "0" else hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
            recipient_hash = hashlib.sha256(tx['recipient'].encode()).hexdigest()[:16] if tx['recipient'] != "0" else "CONTRATO"
            lines.append(f"\n  [Transação #{i+1}]")
            lines.append(f"  TIPO...: {data.get('type')}")
            lines.append(f"  DE.....: {sender_hash}")
            lines.append(f"  PARA...: {recipient_hash}")
            if data.get('type') == 'MINT_TOKEN':
                lines.append(f"  ATIVO..: {payload.get('token_id')}")
            elif data.get('type') == 'CREATE_SALE_CONTRACT':
                lines.append(f"  ATIVO..: {payload.get('token_id')}")
                lines.append(f"  PREÇO..: {payload.get('price')} moedas")
            elif data.get('type') == 'EXECUTE_SALE_CONTRACT':
                lines.append(f"  CONTRATO: {payload.get('contract_id')[:16]}...")
            elif data.get('type') == 'TRANSFER_CURRENCY':
                lines.append(f"  VALOR..: {payload.get('amount')} moedas")

        return "\n".join(lines)
    
    def on_contract_select(self, event):
        selection = self.contracts_table.selection()
        if not selection:
            self.buy_button.configure(state="disabled")
            self.contract_conditions_text.configure(state="normal"); self.contract_conditions_text.delete("1.0", ctk.END); self.contract_conditions_text.configure(state="disabled")
            return
        
        contract_id = selection[0]
        contract = self.blockchain.get_contracts().get(contract_id)
        if contract:
            self.contract_conditions_text.configure(state="normal")
            self.contract_conditions_text.delete("1.0", ctk.END)
            self.contract_conditions_text.insert("1.0", contract.get('conditions', 'Nenhuma condição especificada.'))
            self.contract_conditions_text.configure(state="disabled")

            if contract['status'] == 'OPEN' and contract['seller'] != self.current_user_wallet.public_key and time.time() <= contract['valid_until']:
                self.buy_button.configure(state="normal")
            else:
                self.buy_button.configure(state="disabled")

    def handle_buy_button_click(self):
        selection = self.contracts_table.selection()
        if not selection: return
        contract_id = selection[0]
        contract = self.blockchain.get_contracts().get(contract_id)
        if contract:
            self.execute_purchase(contract_id, contract)

    def on_explorer_token_select(self, event):
        selection = self.all_tokens_table.selection()
        if not selection: return
        token_id = selection[0]
        self.token_history_label.configure(text=f"Histórico do Ativo: {token_id}")
        history = self.blockchain.get_token_history(token_id)
        history_text = json.dumps(history, indent=2, ensure_ascii=False)
        self.token_history_text.configure(state="normal")
        self.token_history_text.delete("1.0", ctk.END)
        self.token_history_text.insert("0.0", history_text)
        self.token_history_text.configure(state="disabled")

    def request_faucet_funds(self):
        self.log_event("FAUCET", "Requisitando 100 moedas de teste.")
        self.blockchain.add_transaction("0", self.current_user_wallet.public_key, "reward", {'type': 'FAUCET'})
        self.mine_block()

    def show_transfer_window(self):
        window = ctk.CTkToplevel(self)
        window.title("Transferir Moedas")
        ctk.CTkLabel(window, text="Endereço Público do Destinatário:").pack(padx=20, pady=5)
        address_entry = ctk.CTkTextbox(window, width=400, height=100)
        address_entry.pack(padx=20, pady=5)
        ctk.CTkLabel(window, text="Quantidade de Moedas:").pack(padx=20, pady=5)
        amount_entry = ctk.CTkEntry(window)
        amount_entry.pack(padx=20, pady=5)
        def submit():
            recipient = address_entry.get("1.0", "end-1c")
            try: amount = int(amount_entry.get())
            except ValueError: return
            if not (recipient and amount > 0): return
            self.log_event("TRANSFERÊNCIA", f"Iniciando transferência de {amount} moedas para {recipient[:20]}...")
            self._create_signed_transaction(recipient, {'type': 'TRANSFER_CURRENCY', 'payload': {'amount': amount}})
            window.destroy()
        ctk.CTkButton(window, text="Assinar e Transferir", command=submit).pack(padx=20, pady=20)
    
    def handle_token_action_click(self, event):
        item_id = self.token_table.focus()
        if not item_id: return
        column = self.token_table.identify_column(event.x)
        if column == '#2':
            self.show_create_contract_window(item_id)
            
    def show_create_contract_window(self, token_id):
        window = ctk.CTkToplevel(self)
        window.grab_set()
        window.focus_force()
        window.title(f"Vender Ativo: {token_id}")
        ctk.CTkLabel(window, text="Preço de Venda (em Moedas):").pack(padx=20, pady=5)
        price_entry = ctk.CTkEntry(window)
        price_entry.pack(padx=20, pady=5)
        
        ctk.CTkLabel(window, text="Válido por (horas):").pack(padx=20, pady=5)
        hours_entry = ctk.CTkEntry(window)
        hours_entry.insert(0, "24")
        hours_entry.pack(padx=20, pady=5)
        
        ctk.CTkLabel(window, text="Condições da Venda (Opcional):").pack(padx=20, pady=5)
        conditions_entry = ctk.CTkTextbox(window, height=100, width=300)
        conditions_entry.pack(padx=20, pady=5)
        def submit():
            try:
                price = int(price_entry.get())
                hours = float(hours_entry.get())
            except ValueError: return
            if not price > 0: return
            
            valid_until_timestamp = time.time() + (hours * 3600)
            conditions = conditions_entry.get("1.0", "end-1c")
            self.log_event("CONTRATO", f"Criando contrato de venda para o ativo '{token_id}' por {price} moedas.")
            self._create_signed_transaction("0", {
                'type': 'CREATE_SALE_CONTRACT', 
                'payload': {'contract_id': str(uuid.uuid4()), 'token_id': token_id, 'price': price, 'conditions': conditions, 'valid_until': valid_until_timestamp}
            })
            window.destroy()
        ctk.CTkButton(window, text="Criar Contrato e Minerar", command=submit).pack(padx=20, pady=20)

    def execute_purchase(self, contract_id, contract):
        price = contract['price']
        balance = self.blockchain.get_balance(self.current_user_wallet.public_key)
        if balance < price:
            self.log_event("ERRO", f"Saldo insuficiente para compra. Saldo: {balance}, Preço: {price}.")
            return
        self.log_event("CONTRATO", f"Executando compra do ativo '{contract['token_id']}'...")
        self._create_signed_transaction(contract['seller'], {'type': 'EXECUTE_SALE_CONTRACT', 'payload': {'contract_id': contract_id}})

    def show_register_asset_window(self):
        window = ctk.CTkToplevel(self)
        window.grab_set()
        window.focus_force()
        window.title("Registrar Novo Ativo")
        ctk.CTkLabel(window, text="ID Único do Ativo (Ex: Matrícula do Imóvel):").pack(padx=20, pady=5)
        token_id_entry = ctk.CTkEntry(window, width=250)
        token_id_entry.pack(padx=20, pady=5)
        def submit():
            token_id = token_id_entry.get()
            if not token_id: return
            self.log_event("CONTRATO", f"Iniciando registro do ativo (token) '{token_id}'.")
            self._create_signed_transaction(self.current_user_wallet.public_key, {'type': 'MINT_TOKEN', 'payload': {'token_id': token_id}})
            window.destroy()
        ctk.CTkButton(window, text="Registrar e Minerar", command=submit).pack(padx=20, pady=20)

    def _create_signed_transaction(self, recipient, data):
        tx_core = {'sender': self.current_user_wallet.public_key, 'recipient': recipient, 'data': data}
        signature = Wallet.sign_transaction(self.current_user_wallet.private_key, tx_core)
        if self.blockchain.add_transaction(tx_core['sender'], tx_core['recipient'], signature, data):
            print("Transação assinada e adicionada à pool.")
            self.mine_block()
        else:
            print("ERRO: Falha na verificação da transação.")

# --- Servidor Flask ---
app_flask = Flask(__name__)
@app_flask.route('/chain', methods=['GET'])
def full_chain():
    return jsonify({'chain': main_app.blockchain.chain, 'length': len(main_app.blockchain.chain)}), 200

@app_flask.route('/new_block', methods=['POST'])
def new_block():
    block = request.get_json()
    if not block: return "Dados do bloco ausentes.", 400
    
    added = main_app.blockchain.add_block(block)
    
    if added:
        main_app.log_event("REDE", f"Bloco #{block['index']} recebido e aceito.")
        main_app.gui_queue.append({"type": "update_display"})
        return "Bloco aceito.", 200
    else:
        main_app.log_event("CONSENSO", "Bloco recebido inválido/fora de ordem. Forçando sincronização.")
        main_app.sync_chain()
        return "Bloco rejeitado, forçando sincronização.", 400

def run_flask_app(port):
    app_flask.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    main_app = MainApplication(port=port)
    main_app.mainloop()