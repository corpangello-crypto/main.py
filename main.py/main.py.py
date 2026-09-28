import sqlite3
import hashlib
from datetime import datetime
import flet as ft

# ==============================================================================
# CAMADA DE BANCO DE DADOS (BACKEND)
# ==============================================================================

class DatabaseManager:
    def __init__(self, db_name="calculadora_app.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'usuario'))
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    acao TEXT NOT NULL
                )
            ''')
            cursor.execute("SELECT * FROM usuarios WHERE username = ?", ('admin',))
            if not cursor.fetchone():
                admin_pass = self.hash_password("admin123")
                cursor.execute(
                    "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)",
                    ('admin', admin_pass, 'admin')
                )
                conn.commit()

    def registrar_log(self, usuario: str, acao: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (timestamp, usuario, acao) VALUES (?, ?, ?)",
                (timestamp, usuario, acao)
            )
            conn.commit()

    def autenticar_usuario(self, username: str, password_puro: str):
        pass_hash = self.hash_password(password_puro)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, role FROM usuarios WHERE username = ? AND password_hash = ?",
                (username, pass_hash)
            )
            row = cursor.fetchone()
            if row:
                user_info = {"id": row[0], "username": row[1], "role": row[2]}
                self.registrar_log(username, "Login realizado com sucesso")
                return True, user_info
            else:
                self.registrar_log(username, "Falha de autenticação")
                return False, None

    def cadastrar_usuario(self, username: str, password_puro: str, role: str = "usuario"):
        if not username or not password_puro:
            return False, "Preencha todos os campos."
        pass_hash = self.hash_password(password_puro)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, pass_hash, role)
                )
                conn.commit()
                return True, "Usuário cadastrado com sucesso!"
        except sqlite3.IntegrityError:
            return False, "Nome de usuário já existe."

    def listar_usuarios(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role FROM usuarios ORDER BY id ASC")
            return cursor.fetchall()

    def remover_usuario(self, user_id: int, admin_atual: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM usuarios WHERE id = ?", (user_id,))
            target = cursor.fetchone()
            if not target:
                return False, "Usuário não encontrado."
            if target[0] == admin_atual:
                return False, "Você não pode se remover durante a sessão."
            cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
            conn.commit()
            self.registrar_log(admin_atual, f"Removeu o usuário '{target[0]}'")
            return True, f"Usuário '{target[0]}' removido."

    def obter_logs(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, usuario, acao FROM logs ORDER BY id DESC")
            return cursor.fetchall()

# ==============================================================================
# INTERFACE GRÁFICA INTERATIVA (FLET)
# ==============================================================================

def main_app(page: ft.Page):
    page.title = "Calculadora Smart"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.window_width = 380
    page.window_height = 700

    db = DatabaseManager()
    usuario_logado = {"info": None}

    def mostrar_snack(mensagem: str, erro: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(mensagem, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if erro else ft.Colors.GREEN_700,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def criar_botao_padrao(texto, acao, cor=ft.Colors.BLUE_700, largura=300):
        return ft.Container(
            content=ft.Row(
                [ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=cor,
            padding=12,
            border_radius=8,
            on_click=acao,
            width=largura,
        )

    # --------------------------------------------------------------------------
    # TELAS DA APLICAÇÃO
    # --------------------------------------------------------------------------

    def ir_para_login():
        usuario_logado["info"] = None
        user_field = ft.TextField(label="Usuário", prefix_icon=ft.Icons.PERSON, border_radius=12)
        pass_field = ft.TextField(label="Senha", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, border_radius=12)

        def realizar_login(e):
            sucesso, user_info = db.autenticar_usuario(user_field.value.strip() if user_field.value else "", pass_field.value or "")
            if sucesso:
                usuario_logado["info"] = user_info
                ir_para_calculadora()
            else:
                mostrar_snack("Credenciais inválidas!", erro=True)

        page.views.clear()
        page.views.append(
            ft.View(
                route="/login",
                controls=[
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                        controls=[
                            ft.Icon(ft.Icons.CALCULATE, size=80, color=ft.Colors.BLUE_400),
                            ft.Text("Calculadora Pro", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text("Acesso Restrito ao Sistema", size=14, color=ft.Colors.GREY_400),
                            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                            user_field,
                            pass_field,
                            criar_botao_padrao("ENTRAR", realizar_login),
                            ft.TextButton("Criar nova conta", on_click=lambda e: ir_para_cadastro()),
                        ]
                    )
                ]
            )
        )
        page.update()

    def ir_para_cadastro():
        user_field = ft.TextField(label="Novo Usuário", prefix_icon=ft.Icons.PERSON_ADD, border_radius=12)
        pass_field = ft.TextField(label="Senha", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE, border_radius=12)

        def cadastrar(e):
            sucesso, msg = db.cadastrar_usuario(user_field.value.strip() if user_field.value else "", pass_field.value or "")
            mostrar_snack(msg, erro=not sucesso)
            if sucesso:
                ir_para_login()

        page.views.clear()
        page.views.append(
            ft.View(
                route="/cadastro",
                controls=[
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True,
                        controls=[
                            ft.Text("Novo Cadastro", size=24, weight=ft.FontWeight.BOLD),
                            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                            user_field,
                            pass_field,
                            criar_botao_padrao("REGISTRAR", cadastrar),
                            ft.TextButton("Voltar para Login", on_click=lambda e: ir_para_login()),
                        ]
                    )
                ]
            )
        )
        page.update()

    def ir_para_calculadora():
        user = usuario_logado["info"]
        display = ft.Text("0", size=40, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT)

        def clique_botao(e):
            tecla = e.control.content.controls[0].value
            if tecla == "C":
                display.value = "0"
            elif tecla == "=":
                try:
                    expr = display.value.replace("×", "*").replace("÷", "/")
                    res = str(eval(expr))
                    db.registrar_log(user["username"], f"Calculou: {display.value} = {res}")
                    display.value = res
                except Exception:
                    display.value = "Erro"
            else:
                if display.value in ["0", "Erro"]:
                    display.value = tecla
                else:
                    display.value += tecla
            page.update()

        botoes = [
            ["C", "(", ")", "÷"],
            ["7", "8", "9", "×"],
            ["4", "5", "6", "-"],
            ["1", "2", "3", "+"],
            ["0", ".", "="]
        ]

        grid_controls = []
        for linha in botoes:
            cols = []
            for btn in linha:
                cor_bg = ft.Colors.ORANGE_800 if btn in ["÷", "×", "-", "+", "="] else (ft.Colors.GREY_800 if btn in ["C", "(", ")"] else ft.Colors.GREY_900)
                expand = 2 if btn == "0" else 1
                cols.append(
                    ft.Container(
                        content=ft.Row(
                            [ft.Text(btn, size=22, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=cor_bg,
                        border_radius=8,
                        on_click=clique_botao,
                        expand=expand,
                        height=60,
                        padding=10,
                    )
                )
            grid_controls.append(ft.Row(controls=cols, expand=True))

        actions = [ft.IconButton(ft.Icons.LOGOUT, on_click=lambda e: ir_para_login(), tooltip="Sair")]
        if user and user["role"] == "admin":
            actions.insert(0, ft.IconButton(ft.Icons.ADMIN_PANEL_SETTINGS, on_click=lambda e: ir_para_admin(), tooltip="Painel Admin"))

        page.views.clear()
        page.views.append(
            ft.View(
                route="/calculadora",
                controls=[
                    ft.AppBar(
                        title=ft.Text(f"Olá, {user['username'] if user else 'Usuário'}"), 
                        actions=actions, 
                        bgcolor=ft.Colors.GREY_900
                    ),
                    ft.Container(
                        content=ft.Row([display], alignment=ft.MainAxisAlignment.END),
                        padding=20,
                        bgcolor=ft.Colors.GREY_900,
                        border_radius=16,
                        height=100
                    ),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ft.Column(controls=grid_controls, expand=True)
                ]
            )
        )
        page.update()

    def ir_para_admin():
        user = usuario_logado["info"]

        novo_user = ft.TextField(label="Usuário")
        nova_senha = ft.TextField(label="Senha", password=True)
        dd_role = ft.Dropdown(
            options=[ft.dropdown.Option("usuario"), ft.dropdown.Option("admin")],
            value="usuario", width=110
        )

        lista_users = ft.ListView(expand=True, spacing=5)
        lista_logs = ft.ListView(expand=True, spacing=5)

        def carregar_dados():
            lista_users.controls.clear()
            for u in db.listar_usuarios():
                u_id, u_name, u_role = u
                lista_users.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.PERSON),
                        title=ft.Text(u_name),
                        subtitle=ft.Text(f"Função: {u_role}"),
                        trailing=ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED_400, on_click=lambda e, uid=u_id: deletar_usuario(uid))
                    )
                )

            lista_logs.controls.clear()
            for l in db.obter_logs():
                data, u_name, acao = l
                lista_logs.controls.append(
                    ft.ListTile(
                        title=ft.Text(f"{u_name}: {acao}"),
                        subtitle=ft.Text(data, size=11),
                        dense=True
                    )
                )
            page.update()

        def criar_usuario_admin(e):
            sucesso, msg = db.cadastrar_usuario(novo_user.value.strip() if novo_user.value else "", nova_senha.value or "", dd_role.value or "usuario")
            mostrar_snack(msg, erro=not sucesso)
            if sucesso:
                novo_user.value = ""
                nova_senha.value = ""
                carregar_dados()

        def deletar_usuario(uid):
            if user:
                sucesso, msg = db.remover_usuario(uid, user["username"])
                mostrar_snack(msg, erro=not sucesso)
                if sucesso:
                    carregar_dados()

        tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(
                    text="Usuários",
                    content=ft.Column(
                        controls=[
                            ft.Row([novo_user, nova_senha, dd_role]),
                            criar_botao_padrao("Adicionar Usuário", criar_usuario_admin),
                            ft.Divider(),
                            lista_users
                        ]
                    )
                ),
                ft.Tab(
                    text="Logs",
                    content=ft.Column(controls=[lista_logs])
                )
            ], expand=True
        )

        page.views.clear()
        page.views.append(
            ft.View(
                route="/admin",
                controls=[
                    ft.AppBar(
                        title=ft.Text("Painel do Administrador"), 
                        leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: ir_para_calculadora()),
                        bgcolor=ft.Colors.GREY_900
                    ),
                    tabs
                ]
            )
        )
        carregar_dados()

    ir_para_login()

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main_app)
    elif hasattr(ft, "app"):
        ft.app(target=main_app)