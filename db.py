import sqlite3
import datetime
import time
import random
import sys
import json
from utils import profile_utils

conn = sqlite3.connect('ranking.db')
cursor = conn.cursor()

def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            vitorias INTEGER DEFAULT 0,
            derrotas INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, guild_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guilds(
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT
            )          
        ''')
    conn.commit()
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loja(
            guild_id INTEGER,
            tipo TEXT,
            product_name TEXT,
            description TEXT, 
            price INTEGER,
            PRIMARY KEY (guild_id, product_name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vip_roles (
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            call_id TEXT,
            PRIMARY KEY (user_id, guild_id)
)           ''')
    conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            user_id INTEGER,
            guild_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, guild_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_time (
            user_id INTEGER,
            guild_id INTEGER,
            seconds INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, guild_id)
        )
    ''')
    conn.commit()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS punishments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,            
            duracao INTEGER,               
            data TEXT NOT NULL,            
            prova TEXT,
            reason TEXT
        )
    ''')
    conn.commit()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boost_xp (
            user_id INTEGER,
            guild_id INTEGER,
            multiplier REAL,
            expires_at INTEGER,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    conn.commit()
     
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            badge_key TEXT NOT NULL,
            acquired_at INTEGER DEFAULT (strftime('%s','now')),
            PRIMARY KEY (user_id, guild_id, badge_key)
        )
        ''')
    conn.commit()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT,
            theme TEXT,
            technologies TEXT,
            start_time TEXT,
            end_time TEXT,
            description TEXT,
            active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            challenge_id INTEGER,
            UNIQUE(guild_id, user_id, challenge_id)
        )
    ''')
    conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            members TEXT NOT NULL
        )
''')
    conn.commit()


# XP INCREMENT
def add_xp(user_id: int, guild_id: int, amount: int):
    ensure_user_exists(user_id, guild_id) 

    try:

        cursor.execute('SELECT xp FROM users WHERE user_id=? AND guild_id=?', (user_id, guild_id))
        row = cursor.fetchone()
        if not row:
            print(f"[WARN] Usuário {user_id} não encontrado na guild {guild_id}.")
            return False

        old_xp = row[0]
        new_xp = old_xp + amount


        cursor.execute('SELECT count FROM messages WHERE user_id=? AND guild_id=?', (user_id, guild_id))
        msg_row = cursor.fetchone()
        mensagens = msg_row[0] if msg_row else 0

        cursor.execute('SELECT seconds FROM call_time WHERE user_id=? AND guild_id=?', (user_id, guild_id))
        call_row = cursor.fetchone()
        call_seconds = call_row[0] if call_row else 0


        old_level = profile_utils.calculate_level(old_xp)["level"]
        new_level = profile_utils.calculate_level(new_xp)["level"]


        cursor.execute('''
            UPDATE users
            SET xp = ?, level = ?
            WHERE user_id = ? AND guild_id = ?
        ''', (new_xp, new_level, user_id, guild_id))
        conn.commit()


        new_badges = profile_utils.check_and_award_badges(
            db=sys.modules[__name__], 
            user_id=user_id,
            guild_id=guild_id,
            xp=new_xp,
            messages=mensagens,
            call_seconds=call_seconds
        )

        result = {
            "old_xp": old_xp,
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": new_level > old_level,
            "new_badges": new_badges
        }

        return result

    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao adicionar XP ao usuário {user_id}: {e}")
        return False
    
    
# EXISTENCE CHECKERS

def user_exists(user_id, guild_id):
    cursor.execute('SELECT 1 FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    return cursor.fetchone() is not None

def guild_exists(guild_id):
    cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? LIMIT 1', (guild_id,))
    return cursor.fetchone() is not None

def ensure_user_exists(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        set_user_data(user_id, guild_id, 0, 0, 0)

def set_user_data(user_id, guild_id, xp, vitorias, derrotas):
    cursor.execute('''
        INSERT INTO users (user_id, guild_id, xp, vitorias, derrotas)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, guild_id) DO UPDATE SET
            xp = excluded.xp,
            vitorias = excluded.vitorias,
            derrotas = excluded.derrotas;
    ''', (user_id, guild_id, xp, vitorias, derrotas))
    conn.commit()

# UPDATE FUNCTIONS DATABASE

def clear_user_data(user_id, guild_id):
    cursor.execute('''
        UPDATE users SET xp = 0, vitorias = 0, derrotas = 0
        WHERE user_id = ? AND guild_id = ?
    ''', (user_id, guild_id))
    conn.commit()

def update_user_data(user_id, guild_id, xp, vitorias, derrotas):
    try:
        level = profile_utils.calculate_level(xp)["level"]

        with conn:
            cursor.execute('''
                UPDATE users SET
                    xp = ?,
                    level = ?,
                    vitorias = ?,
                    derrotas = ?
                WHERE user_id = ? AND guild_id = ?
            ''', (xp, level, vitorias, derrotas, user_id, guild_id))
    except sqlite3.Error as e:
        print(f"[ERRO] Failed to update user data {user_id}: {e}")
        
def update_xp(user_id, guild_id, xp):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        level = profile_utils.calculate_level(xp)["level"]
        cursor.execute('UPDATE users SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?', 
                       (xp, level, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar XP do usuário {user_id}: {e}")
        return None

def update_vitorias(user_id, guild_id, vitorias):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET vitorias = ? WHERE user_id = ? AND guild_id = ?', (vitorias, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar vitórias do usuário {user_id}: {e}")
        return None

def update_derrotas(user_id, guild_id, derrotas):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET derrotas = ? WHERE user_id = ? AND guild_id = ?', (derrotas, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar derrotas do usuário {user_id}: {e}")
        return None

def update_guild_name(guild_id: int, guild_name: str):
    cursor.execute('''
        INSERT INTO guilds (guild_id, guild_name)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET guild_name = excluded.guild_name
    ''', (guild_id, guild_name))
    conn.commit()


# GET FUNCTIONS    
def get_user_data(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] usuario {user_id} não encontrado")
        return None
    try:
        cursor.execute('SELECT xp, level, vitorias, derrotas FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"[ERRO] Falha na requisicao de dados {user_id}: {e}")
        return None

def get_top_users(guild_id):
    cursor.execute(
        "SELECT user_id, xp, vitorias, derrotas FROM users WHERE guild_id = ?",
        (guild_id,)
    )
    return cursor.fetchall()

# DELETE FUNCTIONS

def delete_user(user_id, guild_id):
    try:
        tables_with_user = [
            "users",
            "messages",
            "call_time",
            "punishments",
            "boost_xp",
            "user_badges",
            "vip_roles",
            "casamentos"
        ]
        for table in tables_with_user:
            cursor.execute(f"DELETE FROM {table} WHERE user_id = ? AND guild_id = ?" , (user_id , guild_id))
        conn.commit()
        print(f"✅ Todos os dados do usuário {user_id} no servidor {guild_id} foram removidos.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Erro ao remover usuário {user_id} da guild {guild_id}: {e}")

def delete_guild_data(guild_id: int):
    try:
        tables_with_guild = [
            "users",
            "messages",
            "call_time",
            "punishments",
            "boost_xp",
            "user_badges",
            "vip_roles",
            "loja",
            "casamentos",
            "guilds"
        ]
        for table in tables_with_guild:
            try:
                cursor.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
            except sqlite3.OperationalError:
                print(f"[AVISO] Tabela '{table}' não encontrada — ignorando.")

        conn.commit()
        print(f"✅ Todos os dados do servidor {guild_id} foram removidos com sucesso.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Erro ao remover dados do servidor {guild_id}: {e}")

# RESET FUNCTIONS

def reset_user_xp(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] usuario {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET xp = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[ERRO] Falha na execucao do UPDATE de XP {user_id}: {e}")

def reset_user_lose(user_id, guild_id):
    cursor.execute('UPDATE users SET derrotas = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()

def reset_user_win(user_id, guild_id):
    cursor.execute('UPDATE users SET vitorias = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()

# SHOP FUNCTIONS

def guild_items_exists(guild_id, product_name):
    cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? AND product_name = ?', (guild_id, product_name))
    return cursor.fetchone() is not None

def get_items_shop(guild_id):
    try:
        cursor.execute('SELECT * FROM loja WHERE guild_id=? ORDER BY price DESC', (guild_id,))
        items = cursor.fetchall()
        if not items:
            print(f'[WARNING] Servidor sem items encontrados {guild_id}')
            return None
        return items
    except sqlite3.Error as e:
        print(f'[ERROR] erro ao selecionar items da loja {e}')
        return None

def set_item_shop(guild_id, tipo, product_name, description, price):
    try:
        cursor.execute('''
            INSERT INTO loja (guild_id, tipo, product_name, description, price)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, tipo, product_name, description, price))
        conn.commit()
        print("Item criado com sucesso.")
    except sqlite3.IntegrityError:
        print("Item já existe! Não foi criado.")

def ensure_guild_shop_exists(guild_id):
    try:
        cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? LIMIT 1', (guild_id,))
        result = cursor.fetchone()
        if result is None:
            cursor.execute('''
                INSERT INTO loja (guild_id, product_name, description, price)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, None, None, None))
            conn.commit()
            print(f'[INFO] Loja do servidor inicializada {guild_id}')
        else:
            print(f'[INFO] Loja do servidor já existe para o servidor {guild_id}')
    except sqlite3.Error as e:
        print(f'[ERRO] erro detectado ao verificar a loja do servidor {guild_id} : {e}')


# VIP FUNCTIONS

def get_vip_role(user_id: int, guild_id: int):
    cursor.execute('''
        SELECT role_id, call_id FROM vip_roles
        WHERE user_id = ? AND guild_id = ?
    ''', (str(user_id), str(guild_id)))
    result = cursor.fetchone()
    return (int(result[0]), int(result[1]) if result[1] else None) if result else (None, None)

def save_vip_role(user_id:int, guild_id:int, role_id:int, call_id:int=None):
    cursor.execute('''
        INSERT OR REPLACE INTO vip_roles (user_id, guild_id, role_id, call_id)
        VALUES (?, ?, ?, ?)
    ''', (str(user_id), str(guild_id), str(role_id), str(call_id) if call_id else None))
    conn.commit()

def update_vip_call(user_id: int, guild_id: int, call_id: int):
    cursor.execute('''
        UPDATE vip_roles SET call_id = ?
        WHERE user_id = ? AND guild_id = ?
    ''', (str(call_id), str(user_id), str(guild_id)))
    conn.commit()


def delete_vip_role(user_id: int, guild_id: int):
    cursor.execute('''
        DELETE FROM vip_roles
        WHERE user_id = ? AND guild_id = ?
    ''', (str(user_id), str(guild_id)))
    conn.commit()    
    
    
def increment_message_count(user_id: int, guild_id: int, amount: int = 1):
    cursor.execute('''
        INSERT INTO messages (user_id, guild_id, count)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, guild_id) DO UPDATE SET
            count = count + excluded.count
    ''', (user_id, guild_id, amount))
    conn.commit()

def get_message_count(user_id: int, guild_id: int) -> int:
    cursor.execute(
        "SELECT count FROM messages WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def add_call_time(user_id: int, guild_id: int, seconds: int):
    cursor.execute('''
        INSERT INTO call_time (user_id, guild_id, seconds)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, guild_id) DO UPDATE SET
            seconds = seconds + excluded.seconds
    ''', (user_id, guild_id, seconds))
    conn.commit()

def get_call_time(user_id: int, guild_id: int) -> int:
    cursor.execute(
        "SELECT seconds FROM call_time WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


# PUNISHMENT FUNCTIONS

def add_punishment(user_id: int, guild_id: int, staff_id: int, tipo: str, duracao: int = None, prova: str = None, reason: str = None):
    data = datetime.datetime.utcnow().isoformat() + "Z"
    cursor.execute('''
        INSERT INTO punishments (user_id, staff_id, guild_id, tipo, duracao, data, prova,reason)
        VALUES (?, ?, ?, ?, ?, ?, ?,?)
    ''', (user_id, staff_id, guild_id, tipo, duracao, data, prova, reason))
    conn.commit()

def get_punishments(user_id: int, guild_id: int):
    cursor.execute('''
        SELECT staff_id, tipo, duracao, data, prova, reason
        FROM punishments
        WHERE user_id = ? AND guild_id = ?
        ORDER BY data DESC
    ''', (user_id, guild_id))
    return cursor.fetchall()

def count_punishments(user_id: int, guild_id: int) -> int:
    cursor.execute('SELECT COUNT(*) FROM punishments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    result = cursor.fetchone()
    return result[0] if result else 0    


# BOOST_XP

def set_boost_xp(user_id: int, guild_id: int, multiplier: float, duration: int):

    expires_at = int(time.time()) + duration
    cursor.execute(
        "REPLACE INTO boost_xp (user_id, guild_id, multiplier, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, guild_id, multiplier, expires_at)
    )
    conn.commit()


def check_boost_active(user_id: int, guild_id: int) -> bool:
    
    cursor.execute(
        "SELECT expires_at FROM boost_xp WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    )
    result = cursor.fetchone()
    if not result:
        return False
    return result[0] > int(time.time())


def remove_boost(user_id: int, guild_id: int):
    
    cursor.execute(
        "DELETE FROM boost_xp WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    )
    conn.commit()


def get_active_boost_multiplier(user_id: int, guild_id: int) -> float:
    
    cursor.execute(
        "SELECT multiplier, expires_at FROM boost_xp WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    result = cursor.fetchone()
    if not result:
        return 1.0

    multiplier, expires_at = result
    if expires_at > int(time.time()):
        return multiplier
    else:
        remove_boost(user_id, guild_id)
        return 1.0
    

def cleanup_expired_boosts():

    try:
        current_time = int(time.time())
        cursor.execute("DELETE FROM boost_xp WHERE expires_at <= ?", (current_time,))
        conn.commit()
        print("[INFO] Boosts expirados foram limpos do banco.")
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao limpar boosts expirados: {e}")
    
# BADGES_SYS

def add_user_badge(user_id: int , guild_id: int , badge_key: str):
    cursor.execute('''
        INSERT OR IGNORE INTO user_badges (user_id, guild_id , badge_key)
        VALUES (? , ? , ? )
                   ''',(user_id, guild_id , badge_key))
    conn.commit()
    

def has_user_badge(user_id: int , guild_id : int , badge_key: str) -> bool :
    cursor.execute(
        "SELECT 1 FROM user_badges WHERE user_id = ? AND guild_id = ? AND badge_key = ?",
        (user_id , guild_id , badge_key)
    )
    return cursor.fetchone() is not None


def get_user_badges(user_id: int, guild_id: int):
    cursor.execute('''
        SELECT badge_key, acquired_at
        FROM user_badges
        WHERE user_id = ? AND guild_id = ?
        ORDER BY acquired_at ASC
    ''', (user_id, guild_id))
    rows = cursor.fetchall()
    return [{"badge_key": r[0], "acquired_at": r[1]} for r in rows]   

def get_badge_holders(guild_id: int, badge_key: str):
    cursor.execute('''
        SELECT user_id FROM user_badges
        WHERE guild_id = ? AND badge_key = ?
    ''', (guild_id, badge_key))
    return [r[0] for r in cursor.fetchall()]

def remove_user_badge(user_id: int, guild_id: int, badge_key: str):
    cursor.execute(
        "DELETE FROM user_badges WHERE user_id=? AND guild_id=? AND badge_key=?",
        (user_id, guild_id, badge_key)
    )
    conn.commit()


#MARRIAGE SYSTEM

def salvar_casamento(user_id: int, parceiro_id: int, guild_id: int, cargo_id: int = None):
    cursor.execute('''
        INSERT OR REPLACE INTO casamentos (user_id, parceiro_id, guild_id, cargo_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, parceiro_id, guild_id, cargo_id))
    conn.commit()

def obter_casamento(user_id: int, guild_id: int):
    cursor.execute('''
        SELECT parceiro_id, cargo_id FROM casamentos
        WHERE user_id = ? AND guild_id = ?
    ''', (user_id, guild_id))
    return cursor.fetchone()

def atualizar_cargo_casamento(user_id: int, guild_id: int, cargo_id: int):
    cursor.execute('''
        UPDATE casamentos SET cargo_id = ?
        WHERE user_id = ? AND guild_id = ?
    ''', (cargo_id, user_id, guild_id))
    conn.commit()

def deletar_casamento(user_id: int, guild_id: int):
    cursor.execute('DELETE FROM casamentos WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()

def verificar_casado(user_id: int, guild_id: int) -> bool:
    cursor.execute('SELECT 1 FROM casamentos WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    return cursor.fetchone() is not None

def remove_cargo_casal(cargo_id: int , guild_id: int):
    cursor.execute(
        "DELETE FROM casamentos WHERE cargo_id = ? AND guild_id = ?",
        (cargo_id, guild_id)
    )
    conn.commit()


#RESET DB 

def factory_reset():

    tables_to_clear = [
        "users",
        "guilds",
        "loja",
        "vip_roles",
        "messages",
        "call_time",
        "punishments",
        "boost_xp",
        "user_badges",
        "casamentos"
    ]
    
    try:
        for table in tables_to_clear:
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        print("[INFO] Banco de dados resetado com sucesso (factory_reset).")
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao resetar o banco: {e}")
        

#CHALLENGES FUNCTIONS


def create_challenge(guild_id, name, theme, technologies, start_time, end_time, description):
    try:
        cursor.execute("UPDATE challenges SET active = 0 WHERE guild_id = ?", (guild_id,))
        cursor.execute("""
            INSERT INTO challenges (guild_id, name, theme, technologies, start_time, end_time, description, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (guild_id, name, theme, technologies, start_time, end_time, description))
        conn.commit()
        print(f"[INFO] Novo desafio criado no servidor {guild_id}.")
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao criar desafio no servidor {guild_id}: {e}")

def get_active_challenge(guild_id):
    cursor.execute("SELECT * FROM challenges WHERE guild_id = ? AND active = 1", (guild_id,))
    return cursor.fetchone()

def end_active_challenge(guild_id):
    cursor.execute("UPDATE challenges SET active = 0 WHERE guild_id = ?", (guild_id,))
    conn.commit()
    print(f"[INFO] Desafio ativo encerrado no servidor {guild_id}.")


def add_participant(guild_id, user_id):
    challenge = get_active_challenge(guild_id)
    if not challenge:
        return False
    challenge_id = challenge[0]
    try:
        cursor.execute("""
            INSERT INTO participantes (guild_id, user_id, challenge_id)
            VALUES (?, ?, ?)
        """, (guild_id, user_id, challenge_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def remove_participant(guild_id, user_id):
    challenge = get_active_challenge(guild_id)
    if not challenge:
        return
    challenge_id = challenge[0]
    cursor.execute("DELETE FROM participantes WHERE guild_id = ? AND user_id = ? AND challenge_id = ?", 
                   (guild_id, user_id, challenge_id))
    conn.commit()

def get_participants(guild_id, challenge_id):
    cursor.execute("""
        SELECT user_id FROM participantes
        WHERE guild_id = ? AND challenge_id = ?
    """, (guild_id, challenge_id))
    return [row[0] for row in cursor.fetchall()]


def create_teams_for_challenge(guild_id, challenge_id, num_times=2):
    participants = get_participants(guild_id, challenge_id)
    if not participants:
        return []

    num_times = min(num_times, len(participants))
    random.shuffle(participants)
    teams = []

    for i in range(num_times):
        teams.append({
            "team_name": f"Time {i+1}",
            "members": participants[i::num_times]
        })


    cursor.execute("DELETE FROM teams WHERE guild_id = ? AND challenge_id = ?", (guild_id, challenge_id))
    for team in teams:
        cursor.execute(
            "INSERT INTO teams (guild_id, challenge_id, team_name, members) VALUES (?, ?, ?, ?)",
            (guild_id, challenge_id, team["team_name"], json.dumps(team["members"]))
        )
    conn.commit()
    return teams

def get_teams(guild_id, challenge_id):
    cursor.execute("SELECT team_name, members FROM teams WHERE guild_id = ? AND challenge_id = ?", (guild_id, challenge_id))
    result = []
    for row in cursor.fetchall():
        result.append({
            "team_name": row[0],
            "members": json.loads(row[1])
        })
    return result

def remove_participant_from_team(guild_id, user_id):
    cursor.execute("SELECT id, members FROM teams WHERE guild_id = ?", (guild_id,))
    teams = cursor.fetchall()
    user_id_str = str(user_id)

    for team_id, members_str in teams:
        members = []

        try:
            members = json.loads(members_str)
            if not isinstance(members, list):
                members = [str(members)]
        except json.JSONDecodeError:
            members = [m.strip() for m in members_str.split(",") if m.strip()]

        members = [str(m) for m in members]

        if user_id_str in members:
            members.remove(user_id_str)

            if members:
                cursor.execute(
                    "UPDATE teams SET members = ? WHERE id = ?",
                    (json.dumps(members), team_id)
                )
            else:
                cursor.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            conn.commit()
            print(f"[INFO] Usuário {user_id} removido do time {team_id}.")
            return True

    print(f"[WARN] Usuário {user_id} não encontrado em nenhum time do servidor {guild_id}.")
    return False