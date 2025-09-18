# gui.py
import customtkinter as ctk
from tkinter import ttk

class BlockchainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
       
        self.geometry("1200x800")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Frame de Navegação
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=0, column=0, sticky="nswe")
        self.navigation_frame.grid_rowconfigure(7, weight=1)

        self.app_title = ctk.CTkLabel(self.navigation_frame, text="Menu", font=ctk.CTkFont(size=20, weight="bold"))
        self.app_title.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.main_view_button = ctk.CTkButton(self.navigation_frame, text="Block Explorer")
        self.main_view_button.grid(row=1, column=0, padx=20, pady=10)
        self.profile_button = ctk.CTkButton(self.navigation_frame, text="Meu Perfil")
        self.profile_button.grid(row=2, column=0, padx=20, pady=10)
        self.marketplace_button = ctk.CTkButton(self.navigation_frame, text="Marketplace")
        self.marketplace_button.grid(row=3, column=0, padx=20, pady=10)
        self.explorer_button = ctk.CTkButton(self.navigation_frame, text="Explorador de Ativos")
        self.explorer_button.grid(row=4, column=0, padx=20, pady=10)
        self.audit_button = ctk.CTkButton(self.navigation_frame, text="Auditoria")
        self.audit_button.grid(row=5, column=0, padx=20, pady=10)
        self.sync_button = ctk.CTkButton(self.navigation_frame, text="Sincronizar (Manual)")
        self.sync_button.grid(row=6, column=0, padx=20, pady=10)

        # Frame Principal
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nswe", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self._configure_styles()

        # --- Telas ---
        self.blockchain_frame = self._create_blockchain_explorer_frame()
        self.profile_frame = self._create_profile_frame()
        self.marketplace_frame = self._create_marketplace_frame()
        self.audit_frame = self._create_audit_frame()
        self.explorer_frame = self._create_explorer_frame()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0, rowheight=25)
        style.map('Treeview', background=[('selected', '#22559b')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat", font=('Calibri', 12,'bold'))
        style.map("Treeview.Heading", background=[('active', '#3484F0')])

    def _create_blockchain_explorer_frame(self):
        frame = ctk.CTkFrame(self.main_frame)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2)
        ctk.CTkLabel(frame, text="Block Explorer", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="w")

        # Painel Esquerdo: Lista de Blocos
        left_pane = ctk.CTkFrame(frame)
        left_pane.grid(row=1, column=0, padx=(20,10), pady=10, sticky="nsew")
        left_pane.grid_rowconfigure(1, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left_pane, text="Blocos na Cadeia").pack(pady=5)
        self.blocks_table = ttk.Treeview(left_pane, columns=('index', 'txs', 'hash'), show='headings')
        self.blocks_table.heading('index', text='Índice')
        self.blocks_table.heading('txs', text='Nº Txs')
        self.blocks_table.heading('hash', text='Hash do Bloco')
        self.blocks_table.column('index', width=60, anchor='center')
        self.blocks_table.column('txs', width=60, anchor='center')
        self.blocks_table.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Painel Direito: Detalhes do Bloco Selecionado
        right_pane = ctk.CTkFrame(frame)
        right_pane.grid(row=1, column=1, padx=(10,20), pady=10, sticky="nsew")
        right_pane.grid_rowconfigure(1, weight=1)
        right_pane.grid_columnconfigure(0, weight=1)
        self.block_details_label = ctk.CTkLabel(right_pane, text="Detalhes do Bloco: (Selecione um bloco à esquerda)")
        self.block_details_label.pack(pady=5)
        self.block_details_text = ctk.CTkTextbox(right_pane, font=ctk.CTkFont(family="monospace"))
        self.block_details_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.block_details_text.configure(state="disabled")
        return frame

    def _create_profile_frame(self):
        frame = ctk.CTkFrame(self.main_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(5, weight=1)

        self.username_label = ctk.CTkLabel(frame, text="Bem-vindo, [usuário]", font=ctk.CTkFont(size=20, weight="bold"))
        self.username_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w")
        
        actions_frame = ctk.CTkFrame(frame)
        actions_frame.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="ew")
        self.faucet_button = ctk.CTkButton(actions_frame, text="Receber 100 Moedas de Teste")
        self.faucet_button.pack(side="left", padx=10, pady=10)
        self.transfer_button = ctk.CTkButton(actions_frame, text="Transferir Moedas")
        self.transfer_button.pack(side="left", padx=10, pady=10)
        
        self.balance_value = ctk.CTkLabel(frame, text="Saldo: 0 Moedas", font=ctk.CTkFont(size=16))
        self.balance_value.grid(row=2, column=0, columnspan=2, padx=20, pady=5, sticky="w")
        
        self.my_hash_label = ctk.CTkLabel(frame, text="Minha Hash Pública:", font=ctk.CTkFont(size=16))
        self.my_hash_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.my_hash_value = ctk.CTkLabel(frame, text="---", font=ctk.CTkFont(family="monospace"))
        self.my_hash_value.grid(row=3, column=1, padx=20, pady=(10,0), sticky="w")
        
        self.address_value = ctk.CTkTextbox(frame, height=80)
        self.address_value.grid(row=4, column=0, columnspan=2, padx=20, pady=5, sticky="ew")

        ctk.CTkLabel(frame, text="Meus Ativos (Tokens):", font=ctk.CTkFont(size=16)).grid(row=5, column=0, padx=20, pady=(10,0), sticky="sw")
        self.register_asset_button = ctk.CTkButton(frame, text="Registrar Novo Ativo")
        self.register_asset_button.grid(row=5, column=1, padx=20, pady=(10,0), sticky="se")
        
        self.token_table = ttk.Treeview(frame, columns=('token_id', 'action'), show='headings')
        self.token_table.heading('token_id', text='ID do Ativo')
        self.token_table.heading('action', text='Ação')
        self.token_table.column('action', width=120, anchor='center')
        self.token_table.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        frame.grid_rowconfigure(6, weight=1)
        return frame

    def _create_marketplace_frame(self):
        frame = ctk.CTkFrame(self.main_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=2)
        frame.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(frame, text="Contratos à Venda (Marketplace)", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        self.contracts_table = ttk.Treeview(frame, columns=('contract_id', 'token_id', 'price', 'status', 'seller', 'expires'), show='headings')
        self.contracts_table.heading('contract_id', text='ID Contrato')
        self.contracts_table.heading('token_id', text='ID Ativo')
        self.contracts_table.heading('price', text='Preço')
        self.contracts_table.heading('status', text='Status')
        self.contracts_table.heading('seller', text='Vendedor (Hash)')
        self.contracts_table.heading('expires', text='Expira em')
        self.contracts_table.column('price', anchor='center', width=80)
        self.contracts_table.column('status', anchor='center', width=80)
        self.contracts_table.column('expires', anchor='center', width=150)
        self.contracts_table.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        ctk.CTkLabel(frame, text="Condições do Contrato Selecionado:", font=ctk.CTkFont(size=14)).grid(row=2, column=0, padx=20, pady=(10,0), sticky="w")
        self.contract_conditions_text = ctk.CTkTextbox(frame, height=100)
        self.contract_conditions_text.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.contract_conditions_text.configure(state="disabled")

        self.buy_button = ctk.CTkButton(frame, text="Comprar Ativo Selecionado", state="disabled")
        self.buy_button.grid(row=4, column=0, padx=20, pady=10)
        return frame

    def _create_audit_frame(self):
        frame = ctk.CTkFrame(self.main_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Log de Auditoria da Rede", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.audit_log_text = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="monospace", size=12))
        self.audit_log_text.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.audit_log_text.configure(state="disabled")
        return frame

    def _create_explorer_frame(self):
        frame = ctk.CTkFrame(self.main_frame)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Explorador de Ativos da Rede", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="w")
        
        left_pane = ctk.CTkFrame(frame)
        left_pane.grid(row=1, column=0, padx=(20,10), pady=10, sticky="nsew")
        left_pane.grid_rowconfigure(1, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left_pane, text="Todos os Ativos Registrados").pack(pady=5)
        self.all_tokens_table = ttk.Treeview(left_pane, columns=('token_id', 'owner'), show='headings')
        self.all_tokens_table.heading('token_id', text='ID do Ativo')
        self.all_tokens_table.heading('owner', text='Dono Atual (Hash)')
        self.all_tokens_table.pack(fill="both", expand=True, padx=5, pady=5)
        
        right_pane = ctk.CTkFrame(frame)
        right_pane.grid(row=1, column=1, padx=(10,20), pady=10, sticky="nsew")
        right_pane.grid_rowconfigure(1, weight=1)
        right_pane.grid_columnconfigure(0, weight=1)
        self.token_history_label = ctk.CTkLabel(right_pane, text="Histórico do Ativo: (Selecione um ativo à esquerda)")
        self.token_history_label.pack(pady=5)
        self.token_history_text = ctk.CTkTextbox(right_pane, font=ctk.CTkFont(family="monospace"))
        self.token_history_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.token_history_text.configure(state="disabled")
        return frame