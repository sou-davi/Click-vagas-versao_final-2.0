import json
import sqlite3

from parking_data import new_state

_STORAGE_KEY = "click_vagas_state_v1"


class SQLiteStorage:
    def __init__(self, database_path, preferences, web=False):
        self.connection = sqlite3.connect(database_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.preferences = preferences
        self.web = web
        self._create_schema()

    def _create_schema(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'cliente',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS parking_spots (
                number INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                plate TEXT NOT NULL UNIQUE COLLATE NOCASE,
                owner_username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                spot_number INTEGER NOT NULL UNIQUE REFERENCES parking_spots(number) ON DELETE CASCADE,
                entry TEXT
            );
            """
        )
        self.connection.commit()

    async def carregar_estado(self):
        total_usuarios = self.connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]
        if total_usuarios:
            return self._ler_estado()

        estado = await self._ler_estado_legado()
        self.salvar_estado_local(estado)
        if self.web:
            await self._salvar_snapshot_web(estado)
        else:
            await self.preferences.remove(_STORAGE_KEY)
        return estado

    async def _ler_estado_legado(self):
        salvo = await self.preferences.get(_STORAGE_KEY)
        if isinstance(salvo, str):
            try:
                estado = json.loads(salvo)
                if (
                    isinstance(estado, dict)
                    and isinstance(estado.get("usuarios"), dict)
                    and isinstance(estado.get("vagas"), list)
                ):
                    return estado
            except json.JSONDecodeError:
                pass
        return new_state()

    def _ler_estado(self):
        usuarios = {}
        for nome, senha, tipo, telefone, email in self.connection.execute(
            "SELECT username, password, user_type, phone, email FROM users ORDER BY username"
        ):
            usuarios[nome] = {
                "senha": senha,
                "tipo": tipo,
                "telefone": telefone,
                "email": email,
                "veiculos": [],
            }

        vagas = []
        veiculos_por_vaga = {
            numero: (modelo, placa, dono, entrada)
            for numero, modelo, placa, dono, entrada in self.connection.execute(
                "SELECT spot_number, model, plate, owner_username, entry FROM vehicles"
            )
        }
        for (numero,) in self.connection.execute(
            "SELECT number FROM parking_spots ORDER BY number"
        ):
            veiculo = veiculos_por_vaga.get(numero)
            if veiculo:
                modelo, placa, dono, entrada = veiculo
                vaga = {
                    "numero": numero,
                    "status": "ocupado",
                    "modelo": modelo,
                    "placa": placa,
                    "usuario": dono,
                    "entrada": entrada,
                }
                if dono in usuarios:
                    usuarios[dono]["veiculos"].append(
                        {"modelo": modelo, "placa": placa, "vaga": numero}
                    )
            else:
                vaga = {
                    "numero": numero,
                    "status": "livre",
                    "modelo": None,
                    "placa": None,
                    "usuario": None,
                    "entrada": None,
                }
            vagas.append(vaga)
        return {"usuarios": usuarios, "vagas": vagas}

    def salvar_estado_local(self, estado):
        with self.connection:
            self.connection.execute("DELETE FROM vehicles")
            self.connection.execute("DELETE FROM parking_spots")
            self.connection.execute("DELETE FROM users")

            for nome, usuario in estado.get("usuarios", {}).items():
                self.connection.execute(
                    """INSERT INTO users (username, password, user_type, phone, email)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        nome,
                        str(usuario.get("senha", "")),
                        usuario.get("tipo", "cliente"),
                        usuario.get("telefone", "") or "",
                        usuario.get("email", "") or "",
                    ),
                )

            for vaga in estado.get("vagas", []):
                numero = int(vaga["numero"])
                self.connection.execute(
                    "INSERT INTO parking_spots (number) VALUES (?)", (numero,)
                )

            for vaga in estado.get("vagas", []):
                if vaga.get("status") != "ocupado":
                    continue
                dono = vaga.get("usuario")
                if dono not in estado.get("usuarios", {}):
                    continue
                self.connection.execute(
                    """INSERT INTO vehicles
                       (model, plate, owner_username, spot_number, entry)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        vaga.get("modelo") or "Veículo",
                        (vaga.get("placa") or "").upper(),
                        dono,
                        int(vaga["numero"]),
                        vaga.get("entrada"),
                    ),
                )

    async def salvar_estado(self, estado):
        self.salvar_estado_local(estado)
        if self.web:
            await self._salvar_snapshot_web(estado)

    async def _salvar_snapshot_web(self, estado):
        await self.preferences.set(
            _STORAGE_KEY, json.dumps(estado, ensure_ascii=False)
        )


async def criar_banco(page, preferences):
    if page.web:
        database_path = ":memory:"
    else:
        import os

        import flet as ft

        paths = ft.StoragePaths()
        support_directory = await paths.get_application_support_directory()
        database_path = os.path.join(support_directory, "click_vagas.sqlite3")

    database = SQLiteStorage(database_path, preferences, web=page.web)
    estado = await database.carregar_estado()
    return database, estado
