# main.py
import customtkinter as ctk
from gui import BlockchainApp
from blockchain import Blockchain, TAX_RATE # Importa a taxa
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

# Tenta importar do config.py, mas define padrões se falhar
try:
    from config import GOVERNMENT_PUBLIC_KEY, TAX_AUTHORITY_PUBLIC_KEY
except ImportError:
    print("AVISO: config.py não encontrado ou incompleto. Algumas funcionalidades podem falhar.")
    GOVERNMENT_PUBLIC_KEY = "GOV_KEY_PLACEHOLDER_RUN_SETUP"
    TAX_AUTHORITY_PUBLIC_KEY = "TAX_KEY_PLACEHOLDER_RUN_SETUP"
NETWORK_NODES = ['127.0.0.1:5001', '127.0.0.1:5002', '127.0.0.1:5003', '127.0.0.1:5004', '127.0.0.1:5005']
SYNC_INTERVAL_MS = 10000
LOCALITIES = ["São Paulo", "Rio de Janeiro", "Curitiba", "Recife", "Belo Horizonte"]

# --- Gerenciador de Contas de Usuário ---
class SimpleUserManager:
    def __init__(self, filename="user_accounts.json"):
        self.users_dir = "data/users"
        os.makedirs(self.users_dir, exist_ok=True)
        self.filename = os.path.join(self.users_dir, filename)
        self.accounts = self.load_accounts()

    def load_accounts(self):
        if not os.path.exists(self.filename): return {}
        try:
            with open(self.filename, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {}

    def save_accounts(self):
        with open(self.filename, 'w') as f: json.dump(self.accounts, f, indent=4)

    def register(self, username, password):
        if not (username and password): return False, "Usuário e senha não podem estar em branco."
        if username in self.accounts: return False, "Usuário já existe."
        if username in ["government", "initial_notary", "tax_authority"]: return False, "Este nome de usuário é reservado."

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        wallet = Wallet()
        try:
            if wallet.create_and_save(password, name=username):
                self.accounts[username] = {"password_hash": password_hash, "wallet_name": username}
                self.save_accounts()
                return True, "Usuário registrado com sucesso."
            else:
                 return False, "Erro desconhecido ao criar carteira."
        except Exception as e:
            print(f"Erro ao registrar usuário e criar carteira: {e}")
            priv_path, pub_path = wallet._get_paths(username)
            if os.path.exists(priv_path): os.remove(priv_path)
            if os.path.exists(pub_path): os.remove(pub_path)
            return False, f"Erro ao criar carteira: {e}"

    def login(self, username, password):
        account = self.accounts.get(username)
        wallet_name_to_load = username
        is_official_account = username in ["government", "tax_authority"]

        temp_wallet = Wallet()
        if is_official_account and not temp_wallet.wallet_exists(name=username):
             print(f"ERRO: Carteira para a conta oficial '{username}' não encontrada. Execute setup.py.")
             return None, None

        wallet = Wallet()
        if not wallet.load(password, name=wallet_name_to_load):
            if account:
                print(f"Senha incorreta para o usuário '{username}'.")
            else:
                 print(f"Falha ao carregar carteira '{wallet_name_to_load}'. Senha incorreta ou arquivo inexistente.")
            return None, None

        if is_official_account:
            config_pk_map = {
                "government": GOVERNMENT_PUBLIC_KEY,
                "tax_authority": TAX_AUTHORITY_PUBLIC_KEY
            }
            if wallet.public_key.strip() != config_pk_map.get(username).strip():
                 print(f"ERRO CRÍTICO: Chave pública da carteira '{username}' não corresponde à do config.py!")
                 return None, None
            return username, wallet

        elif account and account["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
             return username, wallet
        else:
             return None, None


# --- Gerenciador de DB Off-Chain (Simulação) ---
class OffChainDBManager:
    """Simula o banco de dados privado (off-chain) de cada cartório."""
    def __init__(self, port):
        self.db_dir = "data/offchain_db"
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_file = os.path.join(self.db_dir, f'offchain_node_{port}.json')
        self.data = self._load_db()

    def _load_db(self):
        if not os.path.exists(self.db_file): return {}
        try:
            with open(self.db_file, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {}

    def _save_db(self):
        with open(self.db_file, 'w') as f: json.dump(self.data, f, indent=4)

    def save_asset_details(self, details_hash, offchain_data):
        """Salva os dados privados associados a um hash."""
        self.data[details_hash] = offchain_data
        self._save_db()
        print(f"[OffChainDB] Dados salvos localmente para o hash: {details_hash[:10]}...")

    def get_asset_details(self, details_hash):
        """Busca dados privados locais pelo hash."""
        return self.data.get(details_hash)


# --- Aplicação Principal ---
class MainApplication(BlockchainApp):
    def __init__(self, port):
        super().__init__()
        self.withdraw()
        self.port = port
        self.title(f"Blockchain Cartório - Nó {self.port}")

        self.user_manager = SimpleUserManager()
        self.db_manager = OffChainDBManager(port)
        self.current_username = None
        self.current_user_wallet = None
        self.is_government = False
        self.is_notary = False
        self.notary_locality = None
        self.chain_lock = threading.Lock()
        self.toast_after_id = None # ID para o timer do toast

        self.blockchain = None
        self.flask_thread = None
        self.gui_queue = []
        self.after(250, self.process_gui_queue)

        self.show_login_register_window()

    def show_message(self, title, message, is_error=False):
        window = ctk.CTkToplevel(self)
        window.grab_set()
        window.focus_force()
        window.title(title)
        color = "#D32F2F" if is_error else "#388E3C"
        window.geometry("350x150")
        window.resizable(False, False)
        main_frame = ctk.CTkFrame(window, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        msg_label = ctk.CTkLabel(main_frame, text=message, text_color=color, font=ctk.CTkFont(size=14), wraplength=300)
        msg_label.pack(expand=True, fill="both")
        ok_button = ctk.CTkButton(main_frame, text="OK", command=window.destroy, width=100)
        ok_button.pack(pady=(10,0), side="bottom")
        self.update_idletasks()
        try:
            app_width = self.winfo_width()
            app_height = self.winfo_height()
            app_x = self.winfo_x()
            app_y = self.winfo_y()
            win_width = 350
            win_height = 150
            x = app_x + (app_width // 2) - (win_width // 2)
            y = app_y + (app_height // 2) - (win_height // 2)
            window.geometry(f"{win_width}x{win_height}+{x}+{y}")
        except Exception:
            window.geometry(f"350x150")

    # --- NOVO: Funções de Toast ---
    def show_toast(self, message):
        """Mostra uma notificação rápida sem pop-up."""
        if self.toast_after_id:
            self.after_cancel(self.toast_after_id) # Cancela o timer anterior se houver
        
        self.toast_label.configure(text=message)
        self.toast_label.place(relx=0.5, rely=0.95, anchor="center")
        self.toast_label.lift()
        self.toast_after_id = self.after(3000, self.hide_toast) # Esconde após 3 segundos

    def hide_toast(self):
        """Esconde a notificação toast."""
        self.toast_label.place_forget()
        self.toast_after_id = None
    # --- Fim das Funções de Toast ---

    def show_login_register_window(self):
        self.login_reg_window = ctk.CTkToplevel(self)
        self.login_reg_window.title("Login / Registro")
        self.login_reg_window.geometry("400x300")
        self.login_reg_window.grab_set()
        self.login_reg_window.focus_force()
        ctk.CTkLabel(self.login_reg_window, text="Nome de Usuário:").pack(pady=(10,0))
        self.username_entry = ctk.CTkEntry(self.login_reg_window, placeholder_text="Ex: lucas, government")
        self.username_entry.pack(pady=5)
        ctk.CTkLabel(self.login_reg_window, text="Senha:").pack(pady=(10,5))
        self.password_entry = ctk.CTkEntry(self.login_reg_window, show="*")
        self.password_entry.pack(pady=5)
        self.msg_label = ctk.CTkLabel(self.login_reg_window, text="")
        self.msg_label.pack(pady=10)
        button_frame = ctk.CTkFrame(self.login_reg_window, fg_color="transparent")
        button_frame.pack(pady=10)
        ctk.CTkButton(button_frame, text="Login", command=self.handle_login).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Registrar", command=self.handle_register).pack(side="left", padx=10)
        self.login_reg_window.protocol("WM_DELETE_WINDOW", self.destroy)

    def handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        uname, wallet_obj = self.user_manager.login(username, password)
        if uname and wallet_obj:
            self.current_username = uname
            self.current_user_wallet = wallet_obj
            self.login_reg_window.destroy()
            self.initialize_blockchain_and_gui()
        else:
            self.msg_label.configure(text="Login falhou. Verifique usuário/senha.", text_color="red")

    def handle_register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        success, message = self.user_manager.register(username, password)
        color = "green" if success else "red"
        self.msg_label.configure(text=message, text_color=color)

    def initialize_blockchain_and_gui(self):
        if not self.current_user_wallet or not self.current_user_wallet.public_key:
             print("ERRO CRÍTICO: Tentando inicializar sem uma carteira carregada.")
             self.destroy(); return

        self.blockchain = Blockchain(
            self.port,
            GOVERNMENT_PUBLIC_KEY,
            TAX_AUTHORITY_PUBLIC_KEY
        )

        my_address = f'127.0.0.1:{self.port}'
        for node_address in NETWORK_NODES:
            if node_address != my_address: self.blockchain.add_node(node_address)

        self.flask_thread = threading.Thread(target=run_flask_app, args=(self.port,), daemon=True)
        self.flask_thread.start()

        self.connect_widgets()
        self.deiconify()

        self.log_event("REDE", "Sincronizando com a rede ao iniciar...")
        self.sync_chain(force_gui_update=True) # Força a primeira atualização
        self.select_frame("profile")
        self.after(SYNC_INTERVAL_MS, self.periodic_sync)

    def update_user_roles(self):
        if not self.current_user_wallet or not self.current_user_wallet.public_key or not self.blockchain: return
        
        user_pk = self.current_user_wallet.public_key.strip()
        self.is_government = (self.current_username == 'government' and user_pk == GOVERNMENT_PUBLIC_KEY.strip())
        authorized_notaries = self.blockchain.state.get('authorized_notaries', set())
        self.is_notary = (user_pk in authorized_notaries)

        if self.is_notary:
             self.notary_locality = self.blockchain.get_notary_locality(user_pk)
        else:
            self.notary_locality = None

        # Atualiza a GUI
        if self.is_government:
            self.username_label.configure(text="Bem-vindo, Governo")
            self.username_icon.configure(text="👑")
            self.log_event("INICIALIZAÇÃO", "Sessão de Governo iniciada.")
        elif self.is_notary:
            name = f"Cartório {hashlib.sha256(user_pk.encode()).hexdigest()[:8]} ({self.notary_locality})"
            self.username_label.configure(text=f"Bem-vindo, {name}")
            self.username_icon.configure(text="⚖️")
            self.log_event("INICIALIZAÇÃO", f"Sessão de Cartório ({self.notary_locality}) iniciada.")
        else:
            self.username_label.configure(text=f"Bem-vindo, {self.current_username} ({hashlib.sha256(user_pk.encode()).hexdigest()[:8]})")
            self.username_icon.configure(text="👤")
            self.log_event("INICIALIZAÇÃO", f"Sessão de Usuário '{self.current_username}' iniciada.")
        self.update_role_based_widgets()

    def update_role_based_widgets(self):
        # Esconde tudo
        self.governance_label.pack_forget()
        self.register_notary_button.pack_forget()
        self.certify_identity_button.pack_forget()
        self.validation_label.pack_forget()
        self.validation_button.pack_forget()
        self.register_asset_button.grid_remove()
        self.notary_list_label.grid_remove()
        self.authorized_notaries_table.grid_remove()
        self.tax_receipts_table.grid_remove() # Esconde recibos por padrão

        # Mostra com base no papel
        if self.is_government:
            self.governance_label.pack(pady=(10,0))
            self.register_notary_button.pack(pady=5)
            self.notary_list_label.grid(row=7, column=0, columnspan=2, padx=20, pady=(20,0), sticky="sw")
            self.authorized_notaries_table.grid(row=8, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")

        elif self.is_notary:
            self.governance_label.pack(pady=(10,0))
            self.certify_identity_button.pack(pady=5)
            self.validation_label.pack(pady=(10,0))
            self.validation_button.pack(pady=5)
            self.register_asset_button.grid(row=5, column=1, padx=20, pady=(10,0), sticky="se")
            self.tax_receipts_table.grid(row=8, column=0, columnspan=2, padx=20, pady=10, sticky="nsew") # Mostra recibos

        else: # Usuário comum
            self.tax_receipts_table.grid(row=8, column=0, columnspan=2, padx=20, pady=10, sticky="nsew") # Mostra recibos


    def connect_widgets(self):
        self.main_view_button.configure(command=lambda: self.select_frame("blockchain"))
        self.profile_button.configure(command=lambda: self.select_frame("profile"))
        self.marketplace_button.configure(command=lambda: self.select_frame("marketplace"))
        self.explorer_button.configure(command=lambda: self.select_frame("explorer"))
        self.audit_button.configure(command=lambda: self.select_frame("audit"))
        self.validation_button.configure(command=lambda: self.select_frame("validation"))
        # CORREÇÃO: Força atualização da GUI ao clicar no botão manual
        self.sync_button.configure(command=lambda: self.sync_chain(force_gui_update=True))
        self.register_asset_button.configure(command=self.show_register_asset_window)
        self.faucet_button.configure(command=self.request_faucet_funds)
        self.transfer_button.configure(command=self.show_transfer_window)
        self.token_table.bind('<ButtonRelease-1>', self.handle_token_action_click)
        self.buy_button.configure(command=self.show_buy_confirmation_window)
        self.contracts_table.bind('<<TreeviewSelect>>', self.on_contract_select)
        self.blocks_table.bind('<<TreeviewSelect>>', self.on_block_select)
        self.all_tokens_table.bind('<ButtonRelease-1>', self.on_explorer_token_select)
        self.register_notary_button.configure(command=self.show_register_notary_window)
        self.certify_identity_button.configure(command=self.show_certify_identity_window)
        self.pending_sales_table.bind('<<TreeviewSelect>>', self.on_pending_sale_select)
        self.approve_sale_button.configure(command=self.handle_approve_sale)
        self.reject_sale_button.configure(command=self.handle_reject_sale)


    def select_frame(self, name):
        if not hasattr(self, 'blockchain_frame'): return
        frames = {
            "blockchain": self.blockchain_frame,
            "profile": self.profile_frame,
            "marketplace": self.marketplace_frame,
            "audit": self.audit_frame,
            "explorer": self.explorer_frame,
            "validation": self.validation_frame
        }
        for f in frames.values(): f.grid_forget()
        frames[name].grid(row=0, column=0, sticky="nsew")
        self.update_role_based_widgets()
        self.update_all_displays() # Atualiza a tela ao trocar

    # CORREÇÃO: Sincronização periódica não força atualização da GUI
    def periodic_sync(self):
        # A sincronização de rede sempre ocorre
        # A atualização da GUI dentro de sync_chain() será condicional
        self.sync_chain(force_gui_update=False)
        if self.winfo_exists():
            self.after(SYNC_INTERVAL_MS, self.periodic_sync)

    def log_event(self, event_type, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{event_type.ljust(12)}] {message}\n"
        self.gui_queue.append({"type": "log", "message": log_message})

    def process_gui_queue(self):
        update_needed = False
        sync_needed = False
        try:
            while self.gui_queue:
                item = self.gui_queue.pop(0)
                if item.get("type") == "log":
                    if hasattr(self, 'audit_log_text') and self.audit_log_text.winfo_exists():
                        self.audit_log_text.configure(state="normal")
                        self.audit_log_text.insert("0.0", item["message"])
                        self.audit_log_text.configure(state="disabled")
                elif item.get("type") == "update_display":
                    update_needed = True
                elif item.get("type") == "sync_chain":
                    sync_needed = True

            if sync_needed:
                self.sync_chain(force_gui_update=True) # Força atualização se veio da rede
            elif update_needed:
                self.update_all_displays()
                self.update_role_based_widgets()
        except Exception as e:
            # print(f"Erro processando fila da GUI: {e}")
            pass
        finally:
            if self.winfo_exists():
                self.after(250, self.process_gui_queue)

    def mine_block(self):
        new_block = None
        with self.chain_lock:
            if not self.blockchain or not self.current_user_wallet:
                self.log_event("MINERAÇÃO", "Blockchain ou carteira não pronta.")
                return
            if not self.blockchain.pending_transactions:
                self.log_event("MINERAÇÃO", "Nenhuma transação pendente para minerar.")
                return
            
            last_block = self.blockchain.last_block
            last_proof = 0
            if last_block:
                last_proof = last_block['proof']
            
            proof = self.blockchain.proof_of_work(last_proof)
            self.blockchain.add_transaction("0", self.current_user_wallet.public_key, "reward", {'type': 'MINING_REWARD'})
            
            previous_hash = '0'
            if last_block:
                previous_hash = self.blockchain.hash(last_block)
                
            new_block = self.blockchain.create_block(proof, previous_hash)
            
        if new_block:
            self.log_event("MINERAÇÃO", f"Novo bloco #{new_block['index']} minerado com sucesso.")
            self.broadcast_new_block(new_block)
            self.gui_queue.append({"type": "update_display"})

    def broadcast_new_block(self, block):
        if not self.blockchain: return
        self.log_event("REDE", f"Transmitindo bloco #{block['index']} para {len(self.blockchain.nodes)} nós.")
        for node_address in self.blockchain.nodes:
            try:
                requests.post(f'http://{node_address}/new_block', json=block, timeout=2)
            except requests.exceptions.RequestException:
                self.log_event("ERRO DE REDE", f"Falha ao contatar o nó {node_address}.")

    # CORREÇÃO: Adicionado 'force_gui_update'
    def sync_chain(self, force_gui_update=False):
        if not self.blockchain: return
        replaced = False
        with self.chain_lock:
            replaced = self.blockchain.resolve_conflicts()
        
        self.update_user_roles()
        
        # Verifica se há pop-ups abertos
        is_popup_open = False
        if not force_gui_update: # Não checa se estamos forçando (ex: clique no botão)
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkToplevel):
                    is_popup_open = True
                    break
        
        # Logica de atualização
        if replaced:
            self.log_event("CONSENSO", "Cadeia local substituída.")
            if not is_popup_open:
                self.update_all_displays()
            else:
                self.log_event("CONSENSO", "Atualização da GUI adiada (pop-up aberto).")
        else:
            self.log_event("CONSENSO", "Cadeia local já está sincronizada.")
            if not is_popup_open:
                self.update_all_displays()
            else:
                self.log_event("CONSENSO", "Atualização da GUI adiada (pop-up aberto).")


    def update_all_displays(self):
        if not self.blockchain or not self.current_user_wallet or not self.winfo_exists() or not hasattr(self, 'address_value'):
             return
        try:
            address = self.current_user_wallet.public_key.strip()
            my_hash = hashlib.sha256(address.encode()).hexdigest()[:16]
            balance = self.blockchain.get_balance(address)

            # Perfil
            self.address_value.configure(state="normal"); self.address_value.delete("1.0", ctk.END); self.address_value.insert("0.0", address); self.address_value.configure(state="disabled")
            self.my_hash_value.configure(text=my_hash)
            self.balance_value.configure(text=f"Saldo: {balance} Moedas")
            for item in self.token_table.get_children(): self.token_table.delete(item)
            tokens = self.blockchain.get_owned_tokens(address)
            for token_id in tokens:
                status = self.blockchain.get_my_token_status(token_id)
                action = "Solicitar Venda" if status == "Em Carteira" else ""
                self.token_table.insert("", "end", values=(token_id, status, action), iid=token_id)
            for item in self.tax_receipts_table.get_children(): self.tax_receipts_table.delete(item)
            receipts = self.blockchain.get_tax_receipts(address)
            for r in receipts:
                 date_str = datetime.fromtimestamp(r['timestamp']).strftime('%d/%m/%Y %H:%M')
                 self.tax_receipts_table.insert("", "end", values=(
                     date_str, r['token_id'], r['price'], r['tax_paid']
                 ))

            # Block Explorer
            for item in self.blocks_table.get_children(): self.blocks_table.delete(item)
            for block in reversed(self.blockchain.chain):
                block_hash = self.blockchain.hash(block)
                self.blocks_table.insert("", "end", values=(block['index'], len(block['transactions']), f"{block_hash[:16]}..."), iid=block['index'])

            # Marketplace
            contracts = self.blockchain.get_contracts()
            for item in self.contracts_table.get_children(): self.contracts_table.delete(item)
            for cid, data in contracts.items():
                seller_hash = hashlib.sha256(data['seller'].encode()).hexdigest()[:16]
                expires_timestamp = data.get('valid_until', 0)
                expires_str = "N/A"
                if expires_timestamp > 0:
                     expires_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(expires_timestamp))
                self.contracts_table.insert("", "end", values=(cid[:8], data['token_id'], data['price'], data['status'], seller_hash, expires_str), iid=cid)

            # Explorador de Ativos
            all_tokens = self.blockchain.state.get('tokens', {})
            all_metadata = self.blockchain.state.get('token_metadata', {})
            for item in self.all_tokens_table.get_children(): self.all_tokens_table.delete(item)
            for token_id, owner_address in all_tokens.items():
                owner_hash = hashlib.sha256(owner_address.encode()).hexdigest()[:16]
                locality = all_metadata.get(token_id, {}).get('locality', 'N/A')
                self.all_tokens_table.insert("", "end", values=(token_id, owner_hash, locality), iid=token_id)

            # Tabela de Cartórios (Governo)
            if self.is_government:
                 for item in self.authorized_notaries_table.get_children(): self.authorized_notaries_table.delete(item)
                 notaries = self.blockchain.state.get('authorized_notaries', set())
                 locations = self.blockchain.state.get('notary_locations', {})
                 for notary_pk in notaries:
                    notary_hash = hashlib.sha256(notary_pk.encode()).hexdigest()[:16]
                    locality = locations.get(notary_pk, "N/A")
                    self.authorized_notaries_table.insert("", "end", values=(f"{notary_hash}...", locality), iid=notary_pk)

            # Tabela de Validação de Vendas (Cartório)
            if self.is_notary and self.notary_locality:
                self.pending_sales_label.configure(text=f"Solicitações em {self.notary_locality}")
                for item in self.pending_sales_table.get_children(): self.pending_sales_table.delete(item)
                requests_list = self.blockchain.get_pending_sale_requests(self.notary_locality)
                for req in requests_list:
                    seller_hash = hashlib.sha256(req['seller'].encode()).hexdigest()[:16]
                    self.pending_sales_table.insert("", "end", values=(
                        req['token_id'], seller_hash, req['price']
                    ), iid=req['request_id'])
        except Exception as e:
            import traceback
            print(f"Erro ao atualizar displays: {e}")
            traceback.print_exc()

    def on_block_select(self, event):
        if not self.blockchain: return
        selection = self.blocks_table.selection()
        if not selection: return
        try:
            block_index = int(selection[0])
            if block_index < 1 or block_index > len(self.blockchain.chain): return
            block = self.blockchain.chain[block_index - 1]
            details = self.format_block_details(block)
            self.block_details_label.configure(text=f"Detalhes do Bloco #{block_index}")
            self.block_details_text.configure(state="normal")
            self.block_details_text.delete("1.0", ctk.END)
            self.block_details_text.insert("0.0", details)
            self.block_details_text.configure(state="disabled")
        except (ValueError, IndexError) as e:
            print(f"Erro ao selecionar bloco: {e}")

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
            sender = tx.get('sender')
            recipient = tx.get('recipient')
            sender_hash = "SISTEMA" if sender == "0" else (hashlib.sha256(sender.encode()).hexdigest()[:16] if sender else "N/A")
            if recipient == "0": recipient_hash = "CONTRATO/REDE"
            elif recipient: recipient_hash = hashlib.sha256(recipient.encode()).hexdigest()[:16]
            else: recipient_hash = "N/A"
            lines.append(f"\n  [Transação #{i+1}]")
            lines.append(f"  TIPO...: {data.get('type', 'Desconhecido')}")
            lines.append(f"  DE.....: {sender_hash}")
            lines.append(f"  PARA...: {recipient_hash}")
            if data.get('type') == 'MINT_TOKEN':
                lines.append(f"  ATIVO..: {payload.get('token_id')}")
                lines.append(f"  TIPO...: {payload.get('asset_type')}")
                lines.append(f"  ÁREA...: {payload.get('area')}")
                lines.append(f"  LOCAL..: {payload.get('locality')}")
                lines.append(f"  HASH D.: {payload.get('details_hash', 'N/A')[:16]}...")
            elif data.get('type') == 'REGISTER_NOTARY':
                lines.append(f"  LOCAL..: {payload.get('locality')}")
            elif data.get('type') == 'REQUEST_SALE_APPROVAL':
                lines.append(f"  ATIVO..: {payload.get('token_id')}")
                lines.append(f"  PREÇO..: {payload.get('price')} moedas")
            elif data.get('type') == 'APPROVE_SALE':
                lines.append(f"  CONTRATO: {payload.get('contract_id', 'N/A')[:16]}...")
            elif data.get('type') == 'REJECT_SALE':
                lines.append(f"  MOTIVO.: {payload.get('reason')}")
            elif data.get('type') == 'EXECUTE_SALE_CONTRACT':
                lines.append(f"  CONTRATO: {payload.get('contract_id', 'N/A')[:16]}...")
            elif data.get('type') == 'TRANSFER_CURRENCY':
                lines.append(f"  VALOR..: {payload.get('amount')} moedas")
        return "\n".join(lines)

    def _format_public_asset_details(self, metadata):
        details = []
        details.append(f"Tipo do Ativo....: {metadata.get('asset_type', 'N/A')}")
        details.append(f"Localização......: {metadata.get('locality', 'N/A')}")
        details.append(f"Área.............: {metadata.get('area', 'N/A')}")
        details.append(f"Cartório Emissor.: {hashlib.sha256(metadata.get('minted_by', '').encode()).hexdigest()[:16]}...")
        details.append(f"Hash do Documento: {metadata.get('details_hash', 'N/A')}")
        return "\n".join(details)

    def on_contract_select(self, event):
        if not self.blockchain: return
        selection = self.contracts_table.selection()
        if not selection:
            self.buy_button.configure(state="disabled")
            self.contract_conditions_text.configure(state="normal"); self.contract_conditions_text.delete("1.0", ctk.END); self.contract_conditions_text.configure(state="disabled")
            return
        contract_id = selection[0]
        contract = self.blockchain.get_contracts().get(contract_id)
        if contract:
            token_id = contract['token_id']
            metadata = self.blockchain.get_token_metadata(token_id)
            public_details = self._format_public_asset_details(metadata)
            self.contract_conditions_text.configure(state="normal")
            self.contract_conditions_text.delete("1.0", ctk.END)
            self.contract_conditions_text.insert("1.0", public_details)
            self.contract_conditions_text.configure(state="disabled")
            if contract['seller'] != self.current_user_wallet.public_key.strip():
                self.buy_button.configure(state="normal")
            else:
                self.buy_button.configure(state="disabled")

    def on_explorer_token_select(self, event):
        if not self.blockchain: return
        token_id = self.all_tokens_table.focus()
        if not token_id: return
        metadata = self.blockchain.get_token_metadata(token_id)
        public_details = self._format_public_asset_details(metadata)
        self.token_details_text.configure(state="normal")
        self.token_details_text.delete("1.0", ctk.END)
        self.token_details_text.insert("0.0", public_details)
        self.token_details_text.configure(state="disabled")
        self.token_history_label.configure(text=f"Histórico do Ativo: {token_id}")
        history_list = self.blockchain.get_token_history(token_id)
        history_text = "\n\n".join(history_list) if history_list else "Nenhum histórico encontrado para este ativo."
        self.token_history_text.configure(state="normal")
        self.token_history_text.delete("1.0", ctk.END)
        self.token_history_text.insert("0.0", history_text)
        self.token_history_text.configure(state="disabled")

    # CORREÇÃO: Modificado para usar o toast
    def request_faucet_funds(self):
        if not self.blockchain or not self.current_user_wallet: return
        
        self._create_signed_transaction(
            recipient=self.current_user_wallet.public_key,
            sender_pk="0",
            data={'type': 'FAUCET'},
            success_message="Moedas de teste solicitadas. Minerando...",
            show_popup_on_success=False # <--- AQUI A MUDANÇA
        )

    def show_transfer_window(self):
        window = ctk.CTkToplevel(self)
        window.title("Transferir Moedas")
        window.grab_set()
        ctk.CTkLabel(window, text="Endereço Público do Destinatário:").pack(padx=20, pady=5)
        address_entry = ctk.CTkTextbox(window, width=400, height=100)
        address_entry.pack(padx=20, pady=5)
        ctk.CTkLabel(window, text="Quantidade de Moedas:").pack(padx=20, pady=5)
        amount_entry = ctk.CTkEntry(window)
        amount_entry.pack(padx=20, pady=5)
        def submit():
            recipient = address_entry.get("1.0", "end-1c").strip()
            try: amount = int(amount_entry.get())
            except ValueError: 
                self.show_message("Erro de Validação", "A quantidade deve ser um número inteiro.", is_error=True)
                return
            if not (recipient and amount > 0): 
                self.show_message("Erro de Validação", "Destinatário e quantidade são obrigatórios.", is_error=True)
                return
            self.log_event("TRANSFERÊNCIA", f"Iniciando transferência de {amount} moedas para {recipient[:20]}...")
            self._create_signed_transaction(
                recipient, 
                {'type': 'TRANSFER_CURRENCY', 'payload': {'amount': amount}},
                success_message="Transferência enviada à rede."
            )
            window.destroy()
        ctk.CTkButton(window, text="Assinar e Transferir", command=submit).pack(padx=20, pady=20)

    def handle_token_action_click(self, event):
        item_id = self.token_table.focus()
        if not item_id: return
        column = self.token_table.identify_column(event.x)
        if column != '#3': return
        values = self.token_table.item(item_id, 'values')
        if values and values[2] == "Solicitar Venda":
            self.show_request_sale_window(item_id)

    def show_request_sale_window(self, token_id):
        window = ctk.CTkToplevel(self)
        window.grab_set(); window.focus_force()
        window.title(f"Solicitar Venda: {token_id[:20]}...")
        ctk.CTkLabel(window, text="Preço de Venda (em Moedas):").pack(padx=20, pady=5)
        price_entry = ctk.CTkEntry(window); price_entry.pack(padx=20, pady=5)
        def submit():
            try:
                price = int(price_entry.get())
            except ValueError: 
                self.show_message("Erro de Validação", "O preço deve ser um número inteiro.", is_error=True)
                return
            if not price > 0: 
                self.show_message("Erro de Validação", "O preço deve ser maior que zero.", is_error=True)
                return
            request_id = str(uuid.uuid4())
            self.log_event("VENDA", f"Enviando solicitação de venda para o ativo '{token_id}' por {price} moedas.")
            self._create_signed_transaction("0", {
                'type': 'REQUEST_SALE_APPROVAL',
                'payload': {
                    'request_id': request_id,
                    'token_id': token_id,
                    'price': price
                }
            }, success_message="Solicitação de venda enviada para aprovação.")
            window.destroy()
        ctk.CTkButton(window, text="Enviar Solicitação e Minerar", command=submit).pack(padx=20, pady=20)


    def show_buy_confirmation_window(self):
        if not self.blockchain: return
        selection = self.contracts_table.selection()
        if not selection: return
        contract_id = selection[0]
        contract = self.blockchain.get_contracts().get(contract_id)
        if not contract: return
        price = contract['price']
        tax = int(price * TAX_RATE)
        total = price + tax
        balance = self.blockchain.get_balance(self.current_user_wallet.public_key)
        window = ctk.CTkToplevel(self)
        window.grab_set(); window.focus_force()
        window.title("Confirmar Compra")
        ctk.CTkLabel(window, text=f"Ativo: {contract['token_id']}", font=ctk.CTkFont(size=14)).pack(padx=20, pady=(10,5))
        ctk.CTkLabel(window, text=f"Vendedor: {hashlib.sha256(contract['seller'].encode()).hexdigest()[:16]}...").pack(padx=20, pady=5)
        ctk.CTkLabel(window, text="-"*20).pack(padx=20, pady=5)
        ctk.CTkLabel(window, text=f"Preço do Ativo: {price} moedas").pack(padx=20, pady=5)
        ctk.CTkLabel(window, text=f"Imposto (ITBI {TAX_RATE*100}%): {tax} moedas").pack(padx=20, pady=5)
        ctk.CTkLabel(window, text=f"Custo Total: {total} moedas", font=ctk.CTkFont(size=16, weight="bold")).pack(padx=20, pady=10)
        ctk.CTkLabel(window, text="-"*20).pack(padx=20, pady=5)
        ctk.CTkLabel(window, text=f"Seu Saldo Atual: {balance} moedas").pack(padx=20, pady=5)
        msg_label = ctk.CTkLabel(window, text="", text_color="red")
        msg_label.pack(pady=5)
        def submit():
            current_balance = self.blockchain.get_balance(self.current_user_wallet.public_key)
            if current_balance < total:
                msg_label.configure(text="Saldo insuficiente para completar a transação.")
                return
            self.execute_purchase(contract_id, contract)
            window.destroy()
        ctk.CTkButton(window, text="Confirmar Pagamento e Transferir", command=submit).pack(padx=20, pady=20)

    def execute_purchase(self, contract_id, contract):
        if not self.blockchain or not self.current_user_wallet: return
        price = contract['price']
        tax = int(price * TAX_RATE)
        total = price + tax
        balance = self.blockchain.get_balance(self.current_user_wallet.public_key)
        if balance < total:
            self.log_event("ERRO", f"Saldo insuficiente. Saldo: {balance}, Custo Total: {total}.")
            self.show_message("Erro na Compra", f"Saldo insuficiente. Você precisa de {total} moedas, mas só tem {balance}.", is_error=True)
            return
        self.log_event("CONTRATO", f"Executando compra do ativo '{contract['token_id']}'...")
        self._create_signed_transaction(
            recipient=contract['seller'],
            data={'type': 'EXECUTE_SALE_CONTRACT', 'payload': {'contract_id': contract_id}},
            success_message="Compra enviada à rede."
        )

    def show_register_asset_window(self):
        if not self.is_notary: return
        self.asset_window = ctk.CTkToplevel(self)
        self.asset_window.grab_set(); self.asset_window.focus_force()
        self.asset_window.title("Registrar Novo Ativo (Cartório)")
        self.asset_window.geometry("800x600")
        scrollable_frame = ctk.CTkScrollableFrame(self.asset_window)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(scrollable_frame, text="Dados Públicos (On-Chain)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Tipo do Ativo (Ex: Terreno Urbano, Apartamento):").pack(anchor="w", padx=20)
        self.asset_type_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_type_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Área (Ex: 450 m²):").pack(anchor="w", padx=20, pady=(10,0))
        self.asset_area_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_area_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Localidade do Ativo (Município/Estado):").pack(anchor="w", padx=20, pady=(10,0))
        self.asset_locality_combo = ctk.CTkComboBox(scrollable_frame, width=350, values=LOCALITIES)
        self.asset_locality_combo.set(self.notary_locality or LOCALITIES[0])
        self.asset_locality_combo.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Dados Privados (Off-Chain)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10), anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Nome Completo do Proprietário:").pack(anchor="w", padx=20)
        self.asset_owner_name_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_owner_name_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="CPF/CNPJ do Proprietário:").pack(anchor="w", padx=20, pady=(10,0))
        self.asset_owner_cpf_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_owner_cpf_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Endereço Completo do Imóvel:").pack(anchor="w", padx=20, pady=(10,0))
        self.asset_full_address_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_full_address_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Link para Documentos (Simulação de Matrícula/Escritura):").pack(anchor="w", padx=20, pady=(10,0))
        self.asset_docs_link_entry = ctk.CTkEntry(scrollable_frame, width=350)
        self.asset_docs_link_entry.insert(0, "http://exemplo.com/doc/matricula_123.pdf")
        self.asset_docs_link_entry.pack(padx=20, pady=5, anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Proprietário (On-Chain)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10), anchor="w")
        ctk.CTkLabel(scrollable_frame, text="Chave Pública do Proprietário:").pack(anchor="w", padx=20)
        self.asset_owner_pk_entry = ctk.CTkTextbox(scrollable_frame, width=700, height=100)
        self.asset_owner_pk_entry.pack(padx=20, pady=5, anchor="w", fill="x")
        ctk.CTkButton(scrollable_frame, text="Assinar Registro e Minerar", command=self.submit_register_asset).pack(padx=20, pady=20, anchor="w")

    def submit_register_asset(self):
        asset_type = self.asset_type_entry.get().strip()
        area = self.asset_area_entry.get().strip()
        locality = self.asset_locality_combo.get()
        owner_name = self.asset_owner_name_entry.get().strip()
        owner_cpf = self.asset_owner_cpf_entry.get().strip()
        full_address = self.asset_full_address_entry.get().strip()
        docs_link = self.asset_docs_link_entry.get().strip()
        owner_public_key = self.asset_owner_pk_entry.get("1.0", "end-1c").strip()
        if not (asset_type and area and locality and owner_name and owner_cpf and full_address and docs_link and owner_public_key):
            self.show_message("Erro de Validação", "Todos os campos são obrigatórios.", is_error=True)
            return
        if locality not in LOCALITIES:
            self.show_message("Erro de Validação", "Localidade inválida.", is_error=True)
            return
        if not owner_public_key.startswith("-----BEGIN PUBLIC KEY-----"):
            self.show_message("Erro de Validação", "Formato da Chave Pública do proprietário inválido.", is_error=True)
            return
        nft_id = str(uuid.uuid4()).upper()[:8]
        token_id = f"{asset_type.replace(' ', '-').upper()}-[{nft_id}]"
        offchain_data = {
            "owner_name": owner_name,
            "owner_cpf_cnpj": owner_cpf,
            "full_address": full_address,
            "documents_link": docs_link,
            "registered_by_notary_pk": self.current_user_wallet.public_key.strip(),
            "registered_at": time.time()
        }
        offchain_json = json.dumps(offchain_data, sort_keys=True)
        details_hash = hashlib.sha256(offchain_json.encode()).hexdigest()
        onchain_payload = {
            'token_id': token_id,
            'asset_type': asset_type,
            'area': area,
            'locality': locality,
            'details_hash': details_hash
        }
        self.db_manager.save_asset_details(details_hash, offchain_data)
        self.log_event("CARTÓRIO", f"Iniciando registro do ativo '{token_id}' em {locality}.")
        self.log_event("CARTÓRIO", f"Hash dos detalhes off-chain: {details_hash[:16]}...")
        self._create_signed_transaction(
            recipient=owner_public_key,
            data={'type': 'MINT_TOKEN', 'payload': onchain_payload},
            success_message="Registro de ativo enviado à rede."
        )
        self.asset_window.destroy()

    # CORREÇÃO: Adicionado 'show_popup_on_success'
    def _create_signed_transaction(self, recipient, data, success_message="Ação enviada à rede.", sender_pk=None, show_popup_on_success=True):
        if sender_pk == "0":
            tx_added = False
            with self.chain_lock:
                 tx_added = self.blockchain.add_transaction("0", recipient, "reward", data)
            if tx_added:
                if show_popup_on_success:
                    self.show_message("Sucesso", success_message)
                else:
                    self.show_toast(success_message) # Usa o toast
                self.mine_block()
                return True
            else:
                self.show_message("Erro", "Falha ao enviar transação do sistema.", is_error=True)
                return False

        if not self.blockchain or not self.current_user_wallet or not self.current_user_wallet.private_key:
             self.log_event("ERRO", "Carteira não carregada ou sem chave privada.")
             self.show_message("Erro de Carteira", "Carteira não carregada ou sem chave privada.", is_error=True)
             return False
        
        sender_pk = self.current_user_wallet.public_key.strip()
        tx_core = {'sender': sender_pk, 'recipient': recipient, 'data': data}
        signature = Wallet.sign_transaction(self.current_user_wallet.private_key, tx_core)

        tx_added = False
        with self.chain_lock:
            if signature:
                 tx_added = self.blockchain.add_transaction(tx_core['sender'], tx_core['recipient'], signature, data)

        if tx_added:
            print("Transação assinada e adicionada à pool. Minerando...")
            if show_popup_on_success:
                self.show_message("Sucesso", success_message)
            else:
                self.show_toast(success_message) # Usa o toast
            self.mine_block()
            return True
        else:
            self.log_event("ERRO", "Falha na criação ou adição da transação. Verifique o log.")
            self.show_message("Erro de Transação", "Falha ao enviar transação. Verifique o log do console.", is_error=True)
            return False

    def show_register_notary_window(self):
        if not self.is_government: return
        window = ctk.CTkToplevel(self)
        window.grab_set(); window.focus_force()
        window.title("Credenciar Novo Cartório")
        ctk.CTkLabel(window, text="Chave Pública Completa do Cartório:").pack(padx=20, pady=(10, 5))
        notary_public_key_entry = ctk.CTkTextbox(window, width=400, height=120)
        notary_public_key_entry.pack(padx=20, pady=5)
        ctk.CTkLabel(window, text="Localidade de Atuação:").pack(padx=20, pady=(10, 5))
        locality_combo = ctk.CTkComboBox(window, width=400, values=LOCALITIES)
        locality_combo.pack(padx=20, pady=5)
        def submit():
            notary_public_key = notary_public_key_entry.get("1.0", "end-1c").strip()
            locality = locality_combo.get()
            if not notary_public_key.startswith("-----BEGIN PUBLIC KEY-----") or not notary_public_key.endswith("-----END PUBLIC KEY-----"):
                self.show_message("Erro de Validação", "Formato da chave pública inválido.", is_error=True)
                return
            if locality not in LOCALITIES:
                self.show_message("Erro de Validação", "Localidade inválida.", is_error=True)
                return
            if notary_public_key == self.current_user_wallet.public_key.strip():
                self.show_message("Erro de Validação", "Não é possível credenciar a si mesmo.", is_error=True)
                return
            self.log_event("GOVERNO", f"Iniciando credenciamento do cartório em {locality}.")
            self._create_signed_transaction(
                recipient=notary_public_key,
                data={'type': 'REGISTER_NOTARY', 'payload': {'locality': locality}},
                success_message="Credenciamento de cartório enviado à rede."
            )
            window.destroy()
        ctk.CTkButton(window, text="Assinar Credenciamento e Minerar", command=submit).pack(padx=20, pady=20)

    def show_certify_identity_window(self):
        if not self.is_notary: return
        window = ctk.CTkToplevel(self)
        window.grab_set(); window.focus_force()
        window.title("Certificar Identidade de Usuário")
        ctk.CTkLabel(window, text="Chave Pública Completa do Usuário:").pack(padx=20, pady=(10, 5))
        user_public_key_entry = ctk.CTkTextbox(window, width=400, height=120)
        user_public_key_entry.pack(padx=20, pady=5)
        def submit():
            user_public_key = user_public_key_entry.get("1.0", "end-1c").strip()
            if not user_public_key.startswith("-----BEGIN PUBLIC KEY-----") or not user_public_key.endswith("-----END PUBLIC KEY-----"):
                self.show_message("Erro de Validação", "Formato da chave pública inválido.", is_error=True)
                return
            self.log_event("CARTÓRIO", f"Iniciando certificação da identidade '{user_public_key[:30]}...'.")
            self._create_signed_transaction(
                recipient=user_public_key,
                data={'type': 'CERTIFY_IDENTITY'},
                success_message="Certificação de identidade enviada à rede."
            )
            window.destroy()
        ctk.CTkButton(window, text="Assinar Certificação e Minerar", command=submit).pack(padx=20, pady=20)

    def on_pending_sale_select(self, event):
        if not self.blockchain or not self.is_notary: return
        selection = self.pending_sales_table.selection()
        if not selection:
            self.approve_sale_button.configure(state="disabled")
            self.reject_sale_button.configure(state="disabled")
            self.sale_details_text.configure(state="normal"); self.sale_details_text.delete("1.0", ctk.END); self.sale_details_text.configure(state="disabled")
            return
        request_id = selection[0]
        request = self.blockchain.state['pending_sale_requests'].get(request_id)
        if not request: return
        token_id = request['token_id']
        metadata_onchain = self.blockchain.get_token_metadata(token_id)
        details_hash = metadata_onchain.get('details_hash')
        details_offchain = self.db_manager.get_asset_details(details_hash)
        details = []
        details.append(f"--- Visão Completa (On-Chain + Off-Chain) ---")
        details.append(f"\nSOLICITAÇÃO: {request_id[:16]}...")
        details.append(f"ATIVO: {token_id}")
        details.append(f"VENDEDOR (Chave): {request['seller'][:40]}...")
        details.append(f"PREÇO: {request['price']} moedas")
        details.append(f"\n--- Detalhes Públicos (On-Chain) ---")
        details.append(f"Tipo do Ativo: {metadata_onchain.get('asset_type', 'N/A')}")
        details.append(f"Área: {metadata_onchain.get('area', 'N/A')}")
        details.append(f"Localidade: {metadata_onchain.get('locality', 'N/A')}")
        details.append(f"Hash (Prova): {details_hash[:32]}...")
        if details_offchain:
            details.append(f"\n--- Detalhes Privados (Off-Chain - Local) ---")
            details.append(f"Proprietário: {details_offchain.get('owner_name', 'N/A')}")
            details.append(f"CPF/CNPJ: {details_offchain.get('owner_cpf_cnpj', 'N/A')}")
            details.append(f"Endereço: {details_offchain.get('full_address', 'N/A')}")
            details.append(f"Documentos: {details_offchain.get('documents_link', 'N/A')}")
        else:
            details.append(f"\n--- Detalhes Privados (Off-Chain - Local) ---")
            details.append(f"!!! DADOS OFF-CHAIN NÃO ENCONTRADOS NO DB LOCAL DESTE NÓ !!!")
            details.append(f"(Este cartório não foi o emissor original?)")
        details.append("\n--- VERIFICAÇÃO (SIMULADO) ---")
        details.append(f"Imóvel Quitado? (Mock): {'Sim' if metadata_onchain.get('paid_off', False) else 'Não'}")
        details.append(f"Pendências Gov? (Mock): {'Não' if not metadata_onchain.get('gov_issues', True) else 'Sim'}")
        self.sale_details_text.configure(state="normal")
        self.sale_details_text.delete("1.0", ctk.END)
        self.sale_details_text.insert("1.0", "\n".join(details))
        self.sale_details_text.configure(state="disabled")
        self.approve_sale_button.configure(state="normal")
        self.reject_sale_button.configure(state="normal")

    def handle_approve_sale(self):
        if not self.is_notary: return
        selection = self.pending_sales_table.selection()
        if not selection: 
            self.show_message("Erro", "Nenhuma solicitação selecionada.", is_error=True)
            return
        request_id = selection[0]
        dialog = ctk.CTkInputDialog(text="Por quantas horas o contrato de venda será válido?", title="Aprovar Venda")
        valid_hours_str = dialog.get_input()
        if not valid_hours_str: return
        try:
            valid_hours = float(valid_hours_str)
            if valid_hours <= 0:
                self.show_message("Erro de Validação", "As horas devem ser um número positivo.", is_error=True)
                return
        except ValueError:
            self.show_message("Erro de Validação", "Valor inválido para horas.", is_error=True)
            return
        contract_id = str(uuid.uuid4())
        valid_until_timestamp = time.time() + (valid_hours * 3600)
        self.log_event("CARTÓRIO", f"Aprovando solicitação {request_id[:8]}... Contrato {contract_id[:8]}... criado.")
        self._create_signed_transaction(
            recipient="0",
            data={
                'type': 'APPROVE_SALE',
                'payload': {
                    'request_id': request_id,
                    'contract_id': contract_id,
                    'valid_until': valid_until_timestamp
                }
            },
            success_message="Aprovação de venda enviada à rede."
        )

    def handle_reject_sale(self):
        if not self.is_notary: return
        selection = self.pending_sales_table.selection()
        if not selection: 
            self.show_message("Erro", "Nenhuma solicitação selecionada.", is_error=True)
            return
        request_id = selection[0]
        dialog = ctk.CTkInputDialog(text="Digite o motivo da recusa (obrigatório):", title="Recusar Venda")
        reason = dialog.get_input()
        if not reason:
            self.show_message("Ação Cancelada", "A recusa foi cancelada ou o motivo estava em branco.", is_error=True)
            return
        self.log_event("CARTÓRIO", f"Rejeitando solicitação {request_id[:8]}... Motivo: {reason}")
        self._create_signed_transaction(
            recipient="0",
            data={
                'type': 'REJECT_SALE',
                'payload': {
                    'request_id': request_id,
                    'reason': reason
                }
            },
            success_message="Recusa de venda enviada à rede."
        )

# --- Servidor Flask ---
app_flask = Flask(__name__)
@app_flask.route('/chain', methods=['GET'])
def full_chain():
    if 'main_app' in globals() and main_app.blockchain is not None:
        return jsonify({'chain': main_app.blockchain.chain, 'length': len(main_app.blockchain.chain)}), 200
    return "Blockchain não inicializada", 503

@app_flask.route('/new_block', methods=['POST'])
def new_block():
    if 'main_app' not in globals() or main_app.blockchain is None:
        return "Blockchain não inicializada", 503
    block = request.get_json()
    if not block: return "Dados do bloco ausentes.", 400
    
    block_accepted = False
    sync_needed = False
    
    with main_app.chain_lock:
        if main_app.blockchain.add_block(block):
            block_accepted = True
        else:
            sync_needed = True
            
    if block_accepted:
        main_app.log_event("REDE", f"Bloco #{block['index']} recebido e aceito.")
        main_app.gui_queue.append({"type": "update_display"})
        return "Bloco aceito.", 200
    else:
        main_app.log_event("CONSENSO", f"Bloco #{block.get('index')} recebido inválido. Enfileirando sincronização.")
        main_app.gui_queue.append({"type": "sync_chain"})
        return "Bloco rejeitado, enfileirando sincronização.", 400

def run_flask_app(port):
    app_flask.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    global main_app
    main_app = MainApplication(port=port)
    main_app.mainloop()

