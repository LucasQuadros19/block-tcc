import customtkinter as ctk
from tkinter import ttk

class BlockchainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Blockchain Cartório - Protótipo")
        self.geometry("1200x800")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Frame de Navegação ---
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=0, column=0, sticky="nswe")
        self.navigation_frame.grid_rowconfigure(9, weight=1) # Ajuste para espaçamento

        self.app_title = ctk.CTkLabel(self.navigation_frame, text="Menu", font=ctk.CTkFont(size=20, weight="bold"))
        self.app_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Botões Padrão
        self.main_view_button = ctk.CTkButton(self.navigation_frame, text="Block Explorer")
        self.main_view_button.grid(row=1, column=0, padx=20, pady=10)
        self.profile_button = ctk.CTkButton(self.navigation_frame, text="Meu Perfil")
        self.profile_button.grid(row=2, column=0, padx=20, pady=10)
        self.marketplace_button = ctk.CTkButton(self.navigation_frame, text="Marketplace (Venda)")
        self.marketplace_button.grid(row=3, column=0, padx=20, pady=10)
        self.explorer_button = ctk.CTkButton(self.navigation_frame, text="Explorador de Ativos")
        self.explorer_button.grid(row=4, column=0, padx=20, pady=10)
        self.audit_button = ctk.CTkButton(self.navigation_frame, text="Auditoria")
        self.audit_button.grid(row=5, column=0, padx=20, pady=10)
        self.sync_button = ctk.CTkButton(self.navigation_frame, text="Sincronizar (Manual)")
        self.sync_button.grid(row=6, column=0, padx=20, pady=10)

        # --- Frame de Cartório (Validação) ---
        self.notary_frame = ctk.CTkFrame(self.navigation_frame, fg_color="transparent")
        self.notary_frame.grid(row=7, column=0, padx=20, pady=10, sticky="s")
        self.validation_label = ctk.CTkLabel(self.notary_frame, text="Ações do Cartório", font=ctk.CTkFont(weight="bold"))
        self.validation_button = ctk.CTkButton(self.notary_frame, text="Validar Vendas")
        # Esconde por padrão
        self.validation_label.pack_forget()
        self.validation_button.pack_forget()


        # --- Frame de Governança ---
        self.governance_frame = ctk.CTkFrame(self.navigation_frame, fg_color="transparent")
        self.governance_frame.grid(row=8, column=0, padx=20, pady=10, sticky="s")
        self.governance_label = ctk.CTkLabel(self.governance_frame, text="Governança", font=ctk.CTkFont(weight="bold"))
        self.register_notary_button = ctk.CTkButton(self.governance_frame, text="Credenciar Cartório")
        self.certify_identity_button = ctk.CTkButton(self.governance_frame, text="Certificar Identidade")
        # Esconde por padrão, o main.py controla a visibilidade
        self.governance_label.pack_forget()
        self.register_notary_button.pack_forget()
        self.certify_identity_button.pack_forget()


        # --- Frame Principal ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nswe", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1) # Faz o frame filho expandir

        self._configure_styles()

        # --- Criação das Telas (Frames Filhos) ---
        # Estas funções apenas criam os frames e seus widgets
        self.blockchain_frame = self._create_blockchain_explorer_frame()
        self.profile_frame = self._create_profile_frame()
        self.marketplace_frame = self._create_marketplace_frame()
        self.audit_frame = self._create_audit_frame()
        self.explorer_frame = self._create_explorer_frame()
        self.validation_frame = self._create_validation_frame() # NOVO FRAME

        # Esconde todos os frames inicialmente, o select_frame controla qual mostrar
        for frame in [self.blockchain_frame, self.profile_frame, self.marketplace_frame, self.audit_frame, self.explorer_frame, self.validation_frame]:
             frame.grid_forget()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        # Configurações de estilo existentes...
        style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0, rowheight=25)
        style.map('Treeview', background=[('selected', '#22559b')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat", font=('Calibri', 12,'bold'))
        style.map("Treeview.Heading", background=[('active', '#3484F0')])

    def _create_blockchain_explorer_frame(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2)
        ctk.CTkLabel(frame, text="Block Explorer", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="w")
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
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1) # Coluna única por padrão
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(6, weight=1) # Tabela de Ativos
        frame.grid_rowconfigure(8, weight=1) # Tabela de Cartórios
        frame.grid_rowconfigure(10, weight=1) # Tabela de Recibos

        # --- Cabeçalho do Perfil com Ícone ---
        header_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w")
        self.username_icon = ctk.CTkLabel(header_frame, text="👤", font=ctk.CTkFont(size=24)) # Ícone Padrão
        self.username_icon.pack(side="left", padx=(0, 10))
        self.username_label = ctk.CTkLabel(header_frame, text="Bem-vindo...", font=ctk.CTkFont(size=20, weight="bold"))
        self.username_label.pack(side="left")

        actions_frame = ctk.CTkFrame(frame, fg_color="transparent")
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
        self.address_value.configure(state="disabled") # Começa desabilitado

        # Tabela de Ativos
        ctk.CTkLabel(frame, text="Meus Ativos (Tokens):", font=ctk.CTkFont(size=16)).grid(row=5, column=0, padx=20, pady=(10,0), sticky="sw")
        self.register_asset_button = ctk.CTkButton(frame, text="Registrar Novo Ativo")
        self.register_asset_button.grid(row=5, column=1, padx=20, pady=(10,0), sticky="se")
        self.register_asset_button.grid_remove() # Esconder inicialmente
        self.token_table = ttk.Treeview(frame, columns=('token_id', 'status', 'action'), show='headings')
        self.token_table.heading('token_id', text='Ativo [Token NFT]')
        self.token_table.heading('status', text='Status')
        self.token_table.heading('action', text='Ação')
        self.token_table.column('token_id', width=300)
        self.token_table.column('status', width=120, anchor='center')
        self.token_table.column('action', width=120, anchor='center')
        self.token_table.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")

        # Tabela de Cartórios Autorizados (apenas para Governo)
        self.notary_list_label = ctk.CTkLabel(frame, text="Cartórios Autorizados:", font=ctk.CTkFont(size=16))
        self.notary_list_label.grid(row=7, column=0, columnspan=2, padx=20, pady=(20,0), sticky="sw")
        self.authorized_notaries_table = ttk.Treeview(frame, columns=('notary_pk_hash', 'location'), show='headings')
        self.authorized_notaries_table.heading('notary_pk_hash', text='Hash do Cartório')
        self.authorized_notaries_table.heading('location', text='Localidade')
        self.authorized_notaries_table.column('notary_pk_hash', width=300)
        self.authorized_notaries_table.column('location', width=150, anchor='center')
        self.authorized_notaries_table.grid(row=8, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        
        # --- NOVA Tabela de Recibos de Imposto ---
        self.tax_receipts_label = ctk.CTkLabel(frame, text="Meus Recibos de Imposto (ITBI):", font=ctk.CTkFont(size=16))
        self.tax_receipts_label.grid(row=9, column=0, columnspan=2, padx=20, pady=(20,0), sticky="sw")
        self.tax_receipts_table = ttk.Treeview(frame, columns=('date', 'token_id', 'price', 'tax_paid'), show='headings')
        self.tax_receipts_table.heading('date', text='Data')
        self.tax_receipts_table.heading('token_id', text='Ativo Comprado')
        self.tax_receipts_table.heading('price', text='Valor (Moedas)')
        self.tax_receipts_table.heading('tax_paid', text='Imposto Pago')
        self.tax_receipts_table.column('date', width=120, anchor='center')
        self.tax_receipts_table.column('token_id', width=250)
        self.tax_receipts_table.column('price', width=100, anchor='e')
        self.tax_receipts_table.column('tax_paid', width=100, anchor='e')
        self.tax_receipts_table.grid(row=10, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")


        # Esconder inicialmente
        self.notary_list_label.grid_remove()
        self.authorized_notaries_table.grid_remove()

        return frame

    def _create_marketplace_frame(self):
        # ... (sem alterações) ...
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=2)
        frame.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(frame, text="Ativos Aprovados para Venda (Marketplace)", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        self.contracts_table = ttk.Treeview(frame, columns=('contract_id', 'token_id', 'price', 'status', 'seller', 'expires'), show='headings')
        self.contracts_table.heading('contract_id', text='ID Contrato')
        self.contracts_table.heading('token_id', text='Ativo [Token NFT]')
        self.contracts_table.heading('price', text='Preço')
        self.contracts_table.heading('status', text='Status')
        self.contracts_table.heading('seller', text='Vendedor (Hash)')
        self.contracts_table.heading('expires', text='Expira em')
        self.contracts_table.column('token_id', width=250)
        self.contracts_table.column('price', anchor='center', width=80)
        self.contracts_table.column('status', anchor='center', width=80)
        self.contracts_table.column('expires', anchor='center', width=150)
        self.contracts_table.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        ctk.CTkLabel(frame, text="Detalhes do Ativo Selecionado:", font=ctk.CTkFont(size=14)).grid(row=2, column=0, padx=20, pady=(10,0), sticky="w")
        self.contract_conditions_text = ctk.CTkTextbox(frame, height=100)
        self.contract_conditions_text.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.contract_conditions_text.configure(state="disabled")
        
        self.buy_button = ctk.CTkButton(frame, text="Verificar Compra...", state="disabled")
        self.buy_button.grid(row=4, column=0, padx=20, pady=10)
        return frame

    def _create_audit_frame(self):
        # ... (sem alterações) ...
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Log de Auditoria da Rede", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.audit_log_text = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="monospace", size=12))
        self.audit_log_text.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.audit_log_text.configure(state="disabled")
        return frame

    def _create_explorer_frame(self):
        # ... (sem alterações) ...
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2) # Mais espaço para o histórico
        ctk.CTkLabel(frame, text="Explorador de Ativos da Rede", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="w")
        left_pane = ctk.CTkFrame(frame)
        left_pane.grid(row=1, column=0, padx=(20,10), pady=10, sticky="nsew")
        left_pane.grid_rowconfigure(1, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left_pane, text="Todos os Ativos Registrados").pack(pady=5)
        self.all_tokens_table = ttk.Treeview(left_pane, columns=('token_id', 'owner', 'locality'), show='headings')
        self.all_tokens_table.heading('token_id', text='Ativo [Token NFT]')
        self.all_tokens_table.heading('owner', text='Dono Atual (Hash)')
        self.all_tokens_table.heading('locality', text='Localidade')
        self.all_tokens_table.column('token_id', width=250)
        self.all_tokens_table.column('owner', width=150)
        self.all_tokens_table.column('locality', width=100, anchor='center')
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

    def _create_validation_frame(self):
        """NOVO: Cria o frame para o cartório validar solicitações de venda."""
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(frame, text="Solicitações de Venda Pendentes", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="w")
        
        # Painel Esquerdo (Lista de Solicitações)
        left_pane = ctk.CTkFrame(frame)
        left_pane.grid(row=1, column=0, padx=(20,10), pady=10, sticky="nsew")
        left_pane.grid_rowconfigure(1, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)
        
        self.pending_sales_label = ctk.CTkLabel(left_pane, text="Solicitações na sua Localidade")
        self.pending_sales_label.pack(pady=5)
        self.pending_sales_table = ttk.Treeview(left_pane, columns=('token_id', 'seller', 'price'), show='headings')
        self.pending_sales_table.heading('token_id', text='Ativo [Token NFT]')
        self.pending_sales_table.heading('seller', text='Vendedor (Hash)')
        self.pending_sales_table.heading('price', text='Preço Sugerido')
        self.pending_sales_table.column('token_id', width=200)
        self.pending_sales_table.column('seller', width=150)
        self.pending_sales_table.column('price', width=80, anchor='e')
        self.pending_sales_table.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Painel Direito (Detalhes da Solicitação)
        right_pane = ctk.CTkFrame(frame)
        right_pane.grid(row=1, column=1, padx=(10,20), pady=10, sticky="nsew")
        right_pane.grid_rowconfigure(1, weight=1)
        right_pane.grid_columnconfigure(0, weight=1)
        
        self.sale_details_label = ctk.CTkLabel(right_pane, text="Detalhes da Solicitação: (Selecione à esquerda)")
        self.sale_details_label.pack(pady=5)
        self.sale_details_text = ctk.CTkTextbox(right_pane, font=ctk.CTkFont(family="monospace"))
        self.sale_details_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.sale_details_text.configure(state="disabled")
        
        button_frame = ctk.CTkFrame(right_pane, fg_color="transparent")
        button_frame.pack(fill="x", padx=5, pady=5)
        self.approve_sale_button = ctk.CTkButton(button_frame, text="Aprovar Venda", state="disabled")
        self.approve_sale_button.pack(side="left", expand=True, padx=5)
        self.reject_sale_button = ctk.CTkButton(button_frame, text="Recusar Venda", state="disabled", fg_color="#D32F2F", hover_color="#B71C1C")
        self.reject_sale_button.pack(side="left", expand=True, padx=5)

        return frame
