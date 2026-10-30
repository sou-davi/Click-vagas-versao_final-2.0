import logging
import re
from datetime import datetime

LOG_LEVEL = logging.INFO
logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("app").setLevel(LOG_LEVEL)
log = logging.getLogger(f"app.{__name__}")

import flet as ft

from parking_data import calcular_tarifa
from pix import gerar_matriz_qr, gerar_payload_pix
from storage import criar_banco

# Cores da marca fornecidas no código original; não há correspondência exata
# para estes dois tons personalizados na paleta ft.Colors.
AZUL = "#0a2540"
LARANJA = "#ff6b35"


class ClickVagasApp:
    def __init__(self, page: ft.Page, database, estado):
        self._page = page
        self.database = database
        self.estado = estado
        self.usuario_logado = None
        self.indice = 0
        self.filtro = "todas"
        self.login_nome = ft.TextField(label="Nome de usuário", width=280, autofocus=True)
        self.login_senha = ft.TextField(label="Senha", width=280, password=True, can_reveal_password=True)
        self.cad_nome = ft.TextField(label="Nome de usuário", width=280)
        self.cad_senha = ft.TextField(label="Senha", width=280, password=True, can_reveal_password=True)
        self.cad_confirmar = ft.TextField(label="Confirmar senha", width=280, password=True, can_reveal_password=True)
        self.cad_telefone = ft.TextField(label="Telefone", width=280, keyboard_type=ft.KeyboardType.PHONE)
        self.cad_email = ft.TextField(label="E-mail", width=280, keyboard_type=ft.KeyboardType.EMAIL)
        self.rec_nome = ft.TextField(label="Nome de usuário", width=280)
        self.rec_senha = ft.TextField(label="Nova senha", width=280, password=True, can_reveal_password=True)
        self.rec_confirmar = ft.TextField(label="Confirmar nova senha", width=280, password=True, can_reveal_password=True)

    async def persistir(self):
        await self.database.salvar_estado(self.estado)

    def mensagem(self, texto):
        self._page.show_dialog(ft.SnackBar(content=ft.Text(texto)))

    def botao_pill(self, texto, callback, cor=AZUL, largura=None):
        return ft.Container(
            width=largura,
            height=46,
            padding=ft.Padding(20, 0, 20, 0),
            border_radius=23,
            bgcolor=cor,
            ink=True,
            alignment=ft.Alignment.CENTER,
            on_click=callback,
            content=ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
        )

    def logo_tile(self, tamanho=150):
        imagem_tamanho = tamanho * 1.35
        return ft.Container(
            width=tamanho,
            height=tamanho,
            border_radius=ft.BorderRadius.all(min(28, tamanho * 0.2)),
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(
                blur_radius=14 if tamanho > 80 else 4,
                spread_radius=2 if tamanho > 80 else 1,
                color=ft.Colors.BLUE_GREY_100,
                offset=ft.Offset(0, 3),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.Alignment.CENTER,
            content=ft.Image(
                src="logoCV.png",
                width=imagem_tamanho,
                height=imagem_tamanho,
                fit=ft.BoxFit.COVER,
                semantics_label="Logotipo Click Vagas",
            ),
        )

    def mostrar_login(self):
        self._page.clean()
        self._page.appbar = None
        self._page.navigation_bar = None
        self._page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.login_nome.error = None
        self.login_senha.error = None
        altura = self._page.height or 700
        tamanho_logo = 90 if altura < 500 else 110 if altura < 650 else 140
        espacamento = 7 if altura < 500 else 10 if altura < 650 else 14
        self._page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=espacamento,
                    controls=[
                        self.logo_tile(tamanho_logo),
                        ft.Text("Click Vagas", size=30, weight=ft.FontWeight.BOLD, color=AZUL),
                        ft.Text("Gestão simples para o seu estacionamento", text_align=ft.TextAlign.CENTER, size=13),
                        self.login_nome,
                        self.login_senha,
                        self.botao_pill("Entrar", self.fazer_login, largura=280),
                        ft.TextButton(content=ft.Text("Esqueceu a senha?"), on_click=self.mostrar_recuperacao),
                        ft.TextButton(content=ft.Text("Criar uma conta"), on_click=self.mostrar_cadastro),
                    ],
                )
            )
        )

    def mostrar_recuperacao(self):
        self._page.clean()
        for campo in (self.rec_nome, self.rec_senha, self.rec_confirmar):
            campo.error = None
        self._page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.START,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        self.logo_tile(130),
                        ft.Text("Redefinir senha", size=27, weight=ft.FontWeight.BOLD, color=AZUL),
                        ft.Text(
                            "Recuperação local, sem validação por e-mail.",
                            size=12,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.GREY_700,
                        ),
                        self.rec_nome,
                        self.rec_senha,
                        self.rec_confirmar,
                        self.botao_pill("Salvar nova senha", self.redefinir_senha, largura=280),
                        ft.TextButton(content=ft.Text("Voltar ao login"), on_click=self.mostrar_login),
                    ],
                ),
            )
        )

    async def redefinir_senha(self):
        nome = (self.rec_nome.value or "").strip()
        senha = self.rec_senha.value or ""
        confirmar = self.rec_confirmar.value or ""
        usuario = self.estado["usuarios"].get(nome)
        self.rec_nome.error = "Informe um nome de usuário" if not nome else None
        if nome and not usuario:
            self.rec_nome.error = "Conta não encontrada neste dispositivo"
        self.rec_senha.error = "Informe a nova senha" if not senha else None
        self.rec_confirmar.error = "As senhas não coincidem" if confirmar != senha else None
        self._page.update()
        if any(campo.error for campo in (self.rec_nome, self.rec_senha, self.rec_confirmar)):
            return
        usuario["senha"] = senha
        await self.persistir()
        self.login_nome.value = nome
        self.login_senha.value = ""
        self.mostrar_login()
        self.mensagem("Senha alterada neste dispositivo.")

    async def fazer_login(self):
        nome = (self.login_nome.value or "").strip()
        senha = self.login_senha.value or ""
        usuario = self.estado["usuarios"].get(nome)
        self.login_nome.error = "Preencha o usuário" if not nome else None
        self.login_senha.error = "Preencha a senha" if not senha else None
        if nome and senha and (not usuario or usuario["senha"] != senha):
            self.login_senha.error = "Usuário ou senha inválidos"
        self._page.update()
        if self.login_nome.error or self.login_senha.error:
            return
        self.usuario_logado = nome
        self.indice = 0
        self.renderizar()

    def mostrar_cadastro(self):
        self._page.clean()
        for campo in (self.cad_nome, self.cad_senha, self.cad_confirmar, self.cad_telefone, self.cad_email):
            campo.error = None
        self._page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.START,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        self.logo_tile(130),
                        ft.Text("Criar conta", size=27, weight=ft.FontWeight.BOLD, color=AZUL),
                        self.cad_nome,
                        self.cad_senha,
                        self.cad_confirmar,
                        self.cad_telefone,
                        self.cad_email,
                        self.botao_pill("Cadastrar", self.cadastrar_usuario, largura=280),
                        ft.TextButton(content=ft.Text("Já tenho conta · Entrar"), on_click=self.mostrar_login),
                    ],
                )
            )
        )

    async def cadastrar_usuario(self):
        nome = (self.cad_nome.value or "").strip()
        senha = self.cad_senha.value or ""
        confirmar = self.cad_confirmar.value or ""
        telefone = (self.cad_telefone.value or "").strip()
        email = (self.cad_email.value or "").strip()
        self.cad_nome.error = "Informe um nome de usuário" if not nome else None
        if nome and nome in self.estado["usuarios"]:
            self.cad_nome.error = "Esse usuário já existe"
        self.cad_senha.error = "Informe uma senha" if not senha else None
        self.cad_confirmar.error = "As senhas não coincidem" if confirmar != senha else None
        self.cad_telefone.error = None
        self.cad_email.error = (
            "E-mail inválido"
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
            else None
        )
        self._page.update()
        if any(
            campo.error
            for campo in (
                self.cad_nome,
                self.cad_senha,
                self.cad_confirmar,
                self.cad_email,
            )
        ):
            return
        self.estado["usuarios"][nome] = {
            "senha": senha,
            "tipo": "cliente",
            "telefone": telefone,
            "email": email,
            "veiculos": [],
        }
        await self.persistir()
        self.login_nome.value = nome
        self.login_senha.value = ""
        self.mostrar_login()

    def ir_para(self, indice):
        if indice == 2 and not self.eh_admin():
            return
        self.indice = indice
        self.renderizar()

    def eh_admin(self):
        usuario = self.estado["usuarios"].get(self.usuario_logado or "", {})
        return usuario.get("tipo") == "admin"

    def renderizar(self):
        if not self.usuario_logado:
            self.mostrar_login()
            return
        telas = [self.view_inicio, self.view_vagas, self.view_relatorio, self.view_sobre, self.view_perfil]
        cabecalho = self.criar_cabecalho()
        self._page.clean()
        self._page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self._page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[cabecalho, telas[self.indice]()],
                ),
            )
        )

    def criar_cabecalho(self):
        itens = [("Início", 0), ("Vagas", 1)]
        if self.eh_admin():
            itens.append(("Relatório", 2))
        itens.extend([("Sobre", 3), ("Perfil", 4)])
        menu = ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
            controls=[
                ft.TextButton(
                    content=ft.Text(rotulo, color=LARANJA if self.indice == indice else ft.Colors.WHITE),
                    on_click=lambda e, i=indice: self.ir_para(i),
                )
                for rotulo, indice in itens
            ],
        )
        return ft.Container(
            bgcolor=AZUL,
            padding=ft.Padding(12, 8, 8, 8),
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        controls=[
                            self.logo_tile(38),
                            ft.Text("Click Vagas", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, expand=True),
                            ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", icon_color=ft.Colors.WHITE, on_click=self.sair),
                        ]
                    ),
                    menu,
                ],
            ),
        )

    def sair(self):
        self.usuario_logado = None
        self.mostrar_login()

    def view_inicio(self):
        vagas = self.estado["vagas"]
        livres = sum(v["status"] == "livre" for v in vagas)
        ocupadas = len(vagas) - livres
        taxa = ocupadas / len(vagas) if vagas else 0
        resumo = ft.Row(
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            controls=[
                self.card_resumo("Vagas livres", livres, ft.Colors.GREEN_700),
                self.card_resumo("Vagas ocupadas", ocupadas, ft.Colors.RED_400),
            ],
        )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(
                    margin=ft.Margin.all(14),
                    padding=ft.Padding(20, 22, 20, 22),
                    border_radius=14,
                    bgcolor=AZUL,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text("Estacione com praticidade.", size=27, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text("Consulte as vagas e acompanhe seu estacionamento em tempo real.", size=14, color=ft.Colors.WHITE),
                            self.botao_pill("Ver vagas", lambda: self.ir_para(1), LARANJA),
                        ],
                    ),
                ),
                ft.Text(f"Olá, {self.usuario_logado}!", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Container(
                    padding=ft.Padding(18, 12, 18, 12),
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[ft.Text("Ocupação"), ft.Text(f"{int(taxa * 100)}%", weight=ft.FontWeight.BOLD)],
                            ),
                            ft.ProgressBar(value=taxa, color=LARANJA, bgcolor=ft.Colors.GREY_300),
                        ]
                    ),
                ),
                resumo,
                ft.Container(height=12),
            ],
        )

    def card_resumo(self, titulo, valor, cor):
        return ft.Card(
            content=ft.Container(
                width=145,
                padding=16,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(str(valor), size=30, weight=ft.FontWeight.BOLD, color=cor),
                        ft.Text(titulo, size=13, text_align=ft.TextAlign.CENTER),
                    ],
                ),
            )
        )

    def view_vagas(self):
        lista = self.estado["vagas"]
        if self.filtro != "todas":
            lista = [v for v in lista if v["status"] == self.filtro]
        return ft.Column(
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    controls=[
                        ft.TextButton(content=ft.Text("Todas"), on_click=lambda: self.mudar_filtro("todas")),
                        ft.TextButton(content=ft.Text("Livres"), on_click=lambda: self.mudar_filtro("livre")),
                        ft.TextButton(content=ft.Text("Ocupadas"), on_click=lambda: self.mudar_filtro("ocupado")),
                    ],
                ),
                ft.ListView(expand=True, spacing=8, padding=12, controls=[self.card_vaga(v) for v in lista]),
            ],
        )

    def mudar_filtro(self, valor):
        self.filtro = valor
        self.renderizar()

    def card_vaga(self, vaga):
        ocupada = vaga["status"] == "ocupado"
        itens = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(f"Vaga {vaga['numero']}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Ocupada" if ocupada else "Livre", color=ft.Colors.RED_600 if ocupada else ft.Colors.GREEN_700),
                ],
            )
        ]
        if ocupada:
            tempo, valor = calcular_tarifa(vaga.get("entrada"))
            itens.extend([
                ft.Text(f"{vaga.get('modelo', '-') } · {vaga.get('placa', '-') }"),
                ft.Text(f"{tempo} · R$ {valor:.2f}", size=13, color=ft.Colors.GREY_700),
                ft.TextButton(content=ft.Text("Liberar vaga"), on_click=lambda e, n=vaga["numero"]: self.liberar_vaga(n)),
            ])
        else:
            itens.append(ft.TextButton(content=ft.Text("Cadastrar veículo"), on_click=lambda e, n=vaga["numero"]: self.abrir_cadastro_veiculo(n)))
        return ft.Card(content=ft.Container(padding=14, content=ft.Column(spacing=6, controls=itens)))

    def abrir_cadastro_veiculo(self, numero=None):
        livres = [v for v in self.estado["vagas"] if v["status"] == "livre"]
        if not livres:
            self.mensagem("Não há vagas livres no momento.")
            return
        modelo = ft.TextField(label="Modelo do veículo", autofocus=True)
        placa = ft.TextField(label="Placa")
        dropdown = None
        if numero is None:
            dropdown = ft.Dropdown(
                label="Escolha uma vaga livre",
                options=[ft.DropdownOption(key=str(v["numero"]), text=f"Vaga {v['numero']}") for v in livres],
            )
            controles = [dropdown, modelo, placa]
        else:
            controles = [ft.Text(f"Vaga selecionada: {numero}", weight=ft.FontWeight.BOLD), modelo, placa]

        async def confirmar():
            num = numero
            if num is None:
                if not dropdown.value:
                    dropdown.error_text = "Selecione uma vaga"
                    self._page.update()
                    return
                num = int(dropdown.value)
            placa_texto = (placa.value or "").strip().upper()
            padrao = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$|^[A-Z]{3}-?[0-9]{4}$"
            modelo.error = None if (modelo.value or "").strip() else "Informe o modelo"
            duplicada = any(v.get("placa") == placa_texto and v["status"] == "ocupado" for v in self.estado["vagas"])
            placa.error = "Informe a placa" if not placa_texto else ("Placa inválida" if not re.match(padrao, placa_texto) else ("Esta placa já está estacionada" if duplicada else None))
            self._page.update()
            if modelo.error or placa.error:
                return
            vaga = next(v for v in self.estado["vagas"] if v["numero"] == num)
            if vaga["status"] != "livre":
                self.mensagem("Essa vaga não está mais livre. Atualize a lista e tente novamente.")
                self._page.pop_dialog()
                return
            vaga.update({"status": "ocupado", "modelo": modelo.value.strip(), "placa": placa_texto, "usuario": self.usuario_logado, "entrada": datetime.now().isoformat()})
            self.estado["usuarios"][self.usuario_logado]["veiculos"].append({"modelo": modelo.value.strip(), "placa": placa_texto, "vaga": num})
            await self.persistir()
            self._page.pop_dialog()
            self.renderizar()

        self._page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Cadastrar veículo"),
                content=ft.Column(tight=True, spacing=10, controls=controles),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=self._page.pop_dialog),
                    ft.Button(content=ft.Text("Salvar"), on_click=confirmar),
                ],
            )
        )

    def controle_qr_pix(self, payload):
        matriz = gerar_matriz_qr(payload)
        modulo = 4
        linhas = [
            ft.Row(
                tight=True,
                spacing=0,
                controls=[
                    ft.Container(
                        width=modulo,
                        height=modulo,
                        bgcolor=ft.Colors.BLACK if escuro else ft.Colors.WHITE,
                    )
                    for escuro in linha
                ],
            )
            for linha in matriz
        ]
        return ft.Container(
            padding=8,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(tight=True, spacing=0, controls=linhas),
        )

    def liberar_vaga(self, numero):
        vaga = next(v for v in self.estado["vagas"] if v["numero"] == numero)
        if not self.eh_admin() and vaga.get("usuario") != self.usuario_logado:
            self.mensagem("Somente o gestor ou responsável pelo veículo pode liberar esta vaga.")
            return
        tempo, valor = calcular_tarifa(vaga.get("entrada"))
        payload_pix = gerar_payload_pix(valor, numero)
        qr_pix = self.controle_qr_pix(payload_pix)

        async def confirmar():
            dono = vaga.get("usuario")
            if dono in self.estado["usuarios"]:
                usuario = self.estado["usuarios"][dono]
                usuario["veiculos"] = [v for v in usuario.get("veiculos", []) if v.get("vaga") != numero]
            vaga.update({"status": "livre", "modelo": None, "placa": None, "usuario": None, "entrada": None})
            await self.persistir()
            self._page.pop_dialog()
            self.renderizar()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Pagamento Pix · vaga {numero}"),
                scrollable=True,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Text(f"Veículo: {vaga.get('modelo')} ({vaga.get('placa')})"),
                        ft.Text(f"Tempo estacionado: {tempo}"),
                        ft.Text(f"Total a pagar: R$ {valor:.2f}", weight=ft.FontWeight.BOLD, color=AZUL),
                        qr_pix,
                        ft.Text(
                            "QR de demonstração. Nenhum pagamento será validado ou cobrado.",
                            text_align=ft.TextAlign.CENTER,
                            size=12,
                        ),
                    ],
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=self._page.pop_dialog),
                    ft.Button(
                        content=ft.Text("Concluir teste e liberar vaga"),
                        bgcolor=LARANJA,
                        on_click=confirmar,
                    ),
                ],
            )
        )

    def view_relatorio(self):
        ocupadas = [v for v in self.estado["vagas"] if v["status"] == "ocupado"]
        itens = []
        for vaga in ocupadas:
            tempo, valor = calcular_tarifa(vaga.get("entrada"))
            entrada = datetime.fromisoformat(vaga["entrada"]).strftime("%H:%M") if vaga.get("entrada") else "-"
            itens.append(
                ft.Card(
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(f"Vaga {vaga['numero']} · {vaga.get('modelo', '-')}", weight=ft.FontWeight.BOLD),
                                ft.Text(f"Placa: {vaga.get('placa', '-')} · Entrada: {entrada}"),
                                ft.Text(f"{tempo} · R$ {valor:.2f}", color=AZUL),
                            ],
                        ),
                    )
                )
            )
        if not itens:
            itens = [ft.Text("Nenhum veículo estacionado no momento.")]
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(padding=16, content=ft.Column(controls=[
                    ft.Text("Relatório gerencial", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Vagas: {len(self.estado['vagas'])} · Ocupadas: {len(ocupadas)} · Livres: {len(self.estado['vagas']) - len(ocupadas)}"),
                    ft.Text("Veículos no estacionamento", size=16, weight=ft.FontWeight.BOLD),
                    *itens,
                ])),
            ],
        )

    def view_sobre(self):
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(height=16),
                self.logo_tile(150),
                ft.Text("Click Vagas", size=27, color=AZUL, weight=ft.FontWeight.BOLD),
                ft.Card(content=ft.Container(width=330, padding=16, content=ft.Column(controls=[
                    ft.Text("Sobre o sistema", size=17, weight=ft.FontWeight.BOLD, color=AZUL),
                    ft.Text("Uma solução prática para acompanhar a ocupação, registrar veículos e consultar informações do estacionamento."),
                ]))),
                ft.Card(content=ft.Container(width=330, padding=16, content=ft.Column(controls=[
                    ft.Text("Recursos", size=17, weight=ft.FontWeight.BOLD, color=AZUL),
                    ft.Text("• Cadastro e liberação de vagas\n• Perfil com veículos\n• Relatório gerencial para gestores\n• Dados mantidos no dispositivo"),
                ]))),
            ],
        )

    def editar_dados_perfil(self):
        usuario = self.estado["usuarios"][self.usuario_logado]
        telefone = ft.TextField(
            label="Telefone",
            value=usuario.get("telefone", ""),
            keyboard_type=ft.KeyboardType.PHONE,
        )
        email = ft.TextField(
            label="E-mail",
            value=usuario.get("email", ""),
            keyboard_type=ft.KeyboardType.EMAIL,
        )

        async def salvar():
            novo_telefone = (telefone.value or "").strip()
            novo_email = (email.value or "").strip()
            email.error = (
                "E-mail inválido"
                if novo_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", novo_email)
                else None
            )
            self._page.update()
            if email.error:
                return
            usuario["telefone"] = novo_telefone
            usuario["email"] = novo_email
            await self.persistir()
            self._page.pop_dialog()
            self.renderizar()
            self.mensagem("Dados cadastrais atualizados.")

        self._page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Editar dados cadastrais"),
                content=ft.Column(tight=True, spacing=10, controls=[telefone, email]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=self._page.pop_dialog),
                    ft.Button(content=ft.Text("Salvar"), on_click=salvar),
                ],
            )
        )

    def editar_veiculo(self, numero):
        vaga = next(
            v
            for v in self.estado["vagas"]
            if v["numero"] == numero and v["status"] == "ocupado"
        )
        modelo = ft.TextField(label="Modelo do veículo", value=vaga.get("modelo", ""))
        placa = ft.TextField(label="Placa", value=vaga.get("placa", ""))

        async def salvar():
            novo_modelo = (modelo.value or "").strip()
            nova_placa = (placa.value or "").strip().upper()
            padrao = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$|^[A-Z]{3}-?[0-9]{4}$"
            duplicada = any(
                outra["numero"] != numero
                and outra["status"] == "ocupado"
                and outra.get("placa", "").upper() == nova_placa
                for outra in self.estado["vagas"]
            )
            modelo.error = None if novo_modelo else "Informe o modelo"
            placa.error = (
                "Informe a placa"
                if not nova_placa
                else "Placa inválida"
                if not re.fullmatch(padrao, nova_placa)
                else "Esta placa já está estacionada"
                if duplicada
                else None
            )
            self._page.update()
            if modelo.error or placa.error:
                return
            vaga["modelo"] = novo_modelo
            vaga["placa"] = nova_placa
            dono = self.estado["usuarios"].get(vaga.get("usuario"), {})
            for veiculo in dono.get("veiculos", []):
                if veiculo.get("vaga") == numero:
                    veiculo.update({"modelo": novo_modelo, "placa": nova_placa})
            await self.persistir()
            self._page.pop_dialog()
            self.renderizar()
            self.mensagem("Veículo atualizado.")

        self._page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Editar veículo · vaga {numero}"),
                content=ft.Column(tight=True, spacing=10, controls=[modelo, placa]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=self._page.pop_dialog),
                    ft.Button(content=ft.Text("Salvar"), on_click=salvar),
                ],
            )
        )

    def view_perfil(self):
        usuario = self.estado["usuarios"][self.usuario_logado]
        veiculos = usuario.get("veiculos", [])
        tipo = "Gestor / Administrador" if usuario.get("tipo") == "admin" else "Cliente"
        itens = [
            ft.Card(
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Text(v["modelo"], weight=ft.FontWeight.BOLD),
                            ft.Text(f"Placa: {v['placa']} · Vaga {v['vaga']}"),
                            ft.TextButton(
                                content=ft.Text("Editar veículo"),
                                on_click=lambda e, n=v["vaga"]: self.editar_veiculo(n),
                            ),
                        ],
                    ),
                )
            )
            for v in veiculos
        ] or [ft.Text("Nenhum veículo cadastrado ainda.")]
        return ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    padding=18,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(self.usuario_logado[:1].upper(), size=28, color=AZUL, weight=ft.FontWeight.BOLD),
                            ft.Text(self.usuario_logado, size=20, weight=ft.FontWeight.BOLD),
                            ft.Text(tipo, color=LARANJA if self.eh_admin() else AZUL),
                            ft.Text(f"Telefone: {usuario.get('telefone') or 'Não informado'}"),
                            ft.Text(f"E-mail: {usuario.get('email') or 'Não informado'}"),
                            ft.Text(f"{len(veiculos)} veículo(s) cadastrado(s)"),
                            ft.Button(content=ft.Text("Editar dados cadastrais"), on_click=self.editar_dados_perfil),
                            ft.Button(content=ft.Text("Adicionar veículo"), on_click=self.abrir_cadastro_veiculo),
                        ],
                    ),
                ),
                ft.ListView(expand=True, spacing=6, padding=12, controls=itens),
            ],
        )


async def main(page: ft.Page):
    page.title = "Click Vagas - Estacionamento"
    page.padding = 0
    # Tom claro estimado a partir do fundo da captura enviada.
    page.bgcolor = "#F5F9FA"
    page.theme_mode = ft.ThemeMode.LIGHT
    preferencias = ft.SharedPreferences()
    database, estado = await criar_banco(page, preferencias)
    app = ClickVagasApp(page, database, estado)
    app.mostrar_login()


ft.run(main)
