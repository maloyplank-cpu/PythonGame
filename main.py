# ВНИМАНИЕ: Этот код требует запуска двух экземпляров одновременно для теста.
# Он также может потребовать разрешения от вашего брандмауэра при первом запуске.

import math
import socket
import threading
import json
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty

# --- Настройки ---
Window.size = (450, 800)
# Цвета
GREEN = (34 / 255, 139 / 255, 34 / 255, 1)
GRAY = (169 / 255, 169 / 255, 169 / 255, 1)
BLUE = (65 / 255, 105 / 255, 225 / 255, 1)
RED = (220 / 255, 20 / 255, 60 / 255, 1)
HP_BAR_GREEN = (0 / 255, 255 / 255, 0 / 255, 1)
HP_BAR_BG = (0, 0, 0, 1)
HAND_BG = (0, 0, 0, 0.4)
CARD_COLOR = (40 / 255, 40 / 255, 60 / 255, 1)

# --- Данные юнитов ---
UNIT_DATA = {
    "Рыцарь": {"color": (0.8, 0.8, 0.8, 1), "hp": 200, "speed": 100, "damage": 20, "attack_speed": 1.0},
    "Гоблин": {"color": (0.1, 0.8, 0.1, 1), "hp": 80, "speed": 180, "damage": 15, "attack_speed": 0.8},
    "Гигант": {"color": (0.9, 0.6, 0.2, 1), "hp": 500, "speed": 60, "damage": 30, "attack_speed": 0.5},
    "Лучник": {"color": (0.9, 0.4, 0.7, 1), "hp": 100, "speed": 110, "damage": 18, "attack_speed": 1.2},
}


# --- СЕТЕВАЯ ЧАСТЬ (без изменений) ---
class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = ""
        self.port = 5555
        self.addr = None
        self.conn = None

    def start_server(self):
        try:
            self.host = socket.gethostbyname(socket.gethostname())
            self.client.bind((self.host, self.port))
            self.client.listen(1)
            return self.host
        except Exception as e:
            print(f"[SERVER ERROR] {e}")
            try:
                self.host = '0.0.0.0'
                self.client.bind((self.host, self.port))
                self.client.listen(1)
                return '127.0.0.1 (или ваш IP)'
            except Exception as e2:
                print(f"[SERVER FALLBACK ERROR] {e2}")
                return None

    def wait_for_connection(self):
        self.conn, self.addr = self.client.accept()
        print("Connected to:", self.addr)
        return True

    def connect(self, host):
        self.host = host
        try:
            self.client.connect((self.host, self.port))
            self.conn = self.client
            return True
        except Exception as e:
            print(f"[CLIENT ERROR] {e}")
            return False

    def send(self, data):
        try:
            message = json.dumps(data).encode('utf-8')
            self.conn.send(message)
        except socket.error as e:
            print(e)

    def receive(self):
        try:
            message = self.conn.recv(2048).decode('utf-8')
            return json.loads(message)
        except (socket.error, json.JSONDecodeError, ConnectionResetError):
            return None


# --- Классы Виджетов ---
class TowerWidget(Widget):
    def __init__(self, max_hp=1000, tower_color=BLUE, **kwargs):
        self.tower_name = kwargs.pop('name', 'default_tower_name')
        super().__init__(**kwargs)
        self.max_hp = max_hp
        self.hp = max_hp
        self.tower_color = tower_color

        with self.canvas:
            self.color_instruction = Color(*self.tower_color)
            self.rect = Rectangle()
        with self.canvas.after:
            self.hp_bar_bg = Rectangle(size=(self.width, 10))
            self.hp_bar = Rectangle(size=(0, 10))

        self.bind(pos=self.update_graphics, size=self.update_graphics)
    def update_graphics(self, *args):
        # Обновляем существующие инструкции
        self.rect.pos = self.pos
        self.rect.size = self.size
        hp_bar_y = self.top + 5
        self.hp_bar_bg.pos = (self.x, hp_bar_y)
        self.hp_bar_bg.size = (self.width, 10)
        current_hp_width = (self.hp / self.max_hp) * self.width if self.hp > 0 else 0
        self.hp_bar.pos = (self.x, hp_bar_y)
        self.hp_bar.size = (current_hp_width, 10)



class UnitWidget(Widget):
    def __init__(self, unit_name, owner='player', **kwargs):
        super().__init__(**kwargs)
        stats = UNIT_DATA[unit_name]
        self.unit_name = unit_name
        self.owner = owner
        self.max_hp = stats["hp"]
        self.hp = self.max_hp
        self.speed = stats["speed"]
        self.damage = stats["damage"]
        self.attack_speed = stats["attack_speed"]
        self.unit_color = stats["color"]
        self.target = None
        self.attack_cooldown = 0
        self.size = (40, 40)
        self.size_hint = (None, None)
        # Создаем инструкции один раз и сохраняем ссылки
        with self.canvas:
            self.color_instruction = Color(*self.unit_color)
            self.rect = Rectangle()
        with self.canvas.after:
            self.hp_bar_bg = Rectangle(size=(self.width, 8))
            self.hp_bar = Rectangle(size=(0, 8))
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        self.update_graphics()  # Первоначальная отрисовка HP

    def update_graphics(self, *args):
        # Обновляем существующие инструкции
        self.rect.pos = self.pos
        self.rect.size = self.size
        hp_bar_y = self.top + 5
        self.hp_bar_bg.pos = (self.x, hp_bar_y)
        self.hp_bar_bg.size = (self.width, 8)
        current_hp_width = (self.hp / self.max_hp) * self.width if self.hp > 0 else 0
        self.hp_bar.pos = (self.x, hp_bar_y)
        self.hp_bar.size = (current_hp_width, 8)


    def find_target(self, enemy_units, enemy_towers):
        self.target = None
        min_dist = float('inf')

        # Ищем ближайшего вражеского юнита
        for unit in enemy_units:
            if unit.hp > 0:
                dist = math.hypot(self.center_x - unit.center_x, self.center_y - unit.center_y)
                if dist < min_dist:
                    min_dist = dist
                    self.target = unit

        # Ищем ближайшую вражескую башню и сравниваем с юнитом
        for tower in enemy_towers:
            if tower.hp > 0:
                dist = math.hypot(self.center_x - tower.center_x, self.center_y - tower.center_y)
                if dist < min_dist:
                    min_dist = dist
                    self.target = tower

    def move(self, dt):
        if not self.target or self.target.hp <= 0:
            return
        if self.collide_widget(self.target):
            self.attack(dt)
            return
        target_pos = self.target.center
        dx, dy = target_pos[0] - self.center_x, target_pos[1] - self.center_y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt

    def attack(self, dt):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
            return
        if self.target and self.target.hp > 0:
            self.target.hp -= self.damage
            self.target.update_graphics()
            self.attack_cooldown = 1.0 / self.attack_speed


class CardWidget(BoxLayout):
    def __init__(self, unit_name, **kwargs):
        super().__init__(**kwargs)
        self.unit_name = unit_name
        self.disabled = False
        self.orientation = 'vertical'
        self.padding = 5
        self.size_hint = (None, None)
        self.size = (90, 120)
        # Создаем инструкции один раз и сохраняем ссылки
        with self.canvas.before:
            Color(*CARD_COLOR)
            self.bg_rect = Rectangle()
        with self.canvas.after:
            self.disabled_color = Color(0, 0, 0, 0) # Initial alpha = 0
            self.disabled_rect = Rectangle()
        stats = UNIT_DATA[unit_name]
        self.add_widget(Label(text=unit_name, font_size='18sp'))
        self.add_widget(Label(text=f"HP: {stats['hp']}", font_size='14sp'))
        self.update_graphics() # Первый вызов для инициализации

    def update_graphics(self, *args):
        # Обновляем существующие инструкции
        self.bg_rect.size = self.size


    def set_disabled(self, is_disabled):
        self.disabled = is_disabled
        # Просто меняем прозрачность оверлея
        self.disabled_color.a = 0.5 if is_disabled else 0


# --- Экраны ---
class MainMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        title = Label(text="Clash Clone", font_size='40sp', size_hint_y=None, height=100)
        play_button = Button(text="Играть", font_size='30sp')
        play_button.bind(on_press=lambda i: setattr(self.manager, 'current', 'game_mode'))
        settings_button = Button(text="Настройки", font_size='30sp', disabled=True)
        quit_button = Button(text="Выход", font_size='30sp')
        quit_button.bind(on_press=lambda i: App.get_running_app().stop())
        layout.add_widget(title)
        layout.add_widget(play_button)
        layout.add_widget(settings_button)
        layout.add_widget(quit_button)
        self.add_widget(layout)


class GameModeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        title = Label(text="Выберите режим", font_size='40sp', size_hint_y=None, height=100)
        create_button = Button(text="Создать игру", font_size='30sp')
        create_button.bind(on_press=self.create_game)
        connect_button = Button(text="Подключиться", font_size='30sp')
        connect_button.bind(on_press=lambda i: setattr(self.manager, 'current', 'connect'))
        play_bot_button = Button(text="Играть с ботом", font_size='30sp')
        play_bot_button.bind(on_press=self.start_bot_game)
        back_button = Button(text="Назад", font_size='30sp', size_hint_y=None, height=60)
        back_button.bind(on_press=lambda i: setattr(self.manager, 'current', 'menu'))
        layout.add_widget(title)
        layout.add_widget(create_button)
        layout.add_widget(connect_button)
        layout.add_widget(play_bot_button)
        layout.add_widget(Label(size_hint_y=0.5))
        layout.add_widget(back_button)
        self.add_widget(layout)

    def create_game(self, instance):
        app = App.get_running_app()
        app.network = Network()
        host_ip = app.network.start_server()
        app.player_role = 'host'
        if host_ip:
            app.player_role = 'host'
            self.manager.get_screen('waiting').set_ip(host_ip)
            self.manager.current = 'waiting'
            threading.Thread(target=self.wait_for_opponent, daemon=True).start()
        else:
            print("Не удалось создать сервер")

    def wait_for_opponent(self):
        app = App.get_running_app()
        if app.network.wait_for_connection():
            Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'game'))

    def start_bot_game(self, instance):
        app = App.get_running_app()
        app.player_role = 'single_player'
        app.network = None
        self.manager.current = 'game'


class ConnectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        title = Label(text="Введите IP адрес", font_size='30sp', size_hint_y=None, height=80)
        self.ip_input = TextInput(multiline=False, font_size='30sp', size_hint_y=None, height=60)
        connect_button = Button(text="Подключиться", font_size='30sp')
        connect_button.bind(on_press=self.connect_to_game)
        back_button = Button(text="Назад", font_size='30sp', size_hint_y=None, height=60)
        back_button.bind(on_press=lambda i: setattr(self.manager, 'current', 'game_mode'))
        layout.add_widget(title)
        layout.add_widget(self.ip_input)
        layout.add_widget(connect_button)
        layout.add_widget(Label())
        layout.add_widget(back_button)
        self.add_widget(layout)

    def connect_to_game(self, instance):
        ip = self.ip_input.text
        app = App.get_running_app()
        app.network = Network()
        if app.network.connect(ip):
            app.player_role = 'client'
            self.manager.current = 'game'
        else:
            print(f"Не удалось подключиться к {ip}")


class WaitingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        self.ip_label = Label(text="Ваш IP: ...", font_size='30sp')
        info_label = Label(text="Ожидание подключения второго игрока...", font_size='20sp')
        layout.add_widget(self.ip_label)
        layout.add_widget(info_label)
        self.add_widget(layout)

    def set_ip(self, ip):
        self.ip_label.text = f"Ваш IP: {ip}"


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game_area = FloatLayout(size_hint=(1, 1))
        self.ui_area = BoxLayout(size_hint_y=None, height=150, padding=10, spacing=10)
        # Создаем корневой BoxLayout, который будет занимать весь экран
        root_layout = BoxLayout(orientation='vertical', size_hint=(1, 1))
        # Сначала добавляем игровое поле (оно займет все доступное место)
        root_layout.add_widget(self.game_area)
        # Затем добавляем UI внизу
        root_layout.add_widget(self.ui_area)
        self.add_widget(root_layout)
        self.towers = []
        self.units = []
        self.selected_card = None
        self.ghost_unit = None
        self.game_over = False
        self.bot_spawn_timer = 0
        self.game_area.bind(size=self.update_layout)
        self.create_ui()

    def on_enter(self, *args):
        self.game_over = False
        if not self.towers:
            self.create_towers()
        for unit in self.units:
            self.game_area.remove_widget(unit)
        self.units.clear()
        for tower in self.towers:
            tower.hp = tower.max_hp
            tower.update_graphics()

        self.bot_spawn_timer = 3.0
        self.game_loop_event = Clock.schedule_interval(self.update, 1.0 / 60.0)

        app = App.get_running_app()
        if app.network:
            self.network_loop_event = Clock.schedule_interval(self.check_network, 1.0 / 30.0)

    def on_leave(self, *args):
        self.game_loop_event.cancel()
        if hasattr(self, 'network_loop_event'):
            self.network_loop_event.cancel()
            del self.network_loop_event

    def check_network(self, dt):
        app = App.get_running_app()
        if not app.network:
            return
        data = app.network.receive()
        if data:
            if data['action'] == 'spawn':
                self.spawn_opponent_unit(data)
            elif data['action'] == 'game_over':
                self.end_game(data['message'])

    def spawn_opponent_unit(self, data):
        unit_name = data['unit']
        original_pos = data['pos']

        # Противник всегда появляется на "перевернутой" по вертикали позиции
        spawn_pos = (original_pos[0], self.game_area.height - original_pos[1])
        unit = UnitWidget(unit_name, owner='opponent', center=spawn_pos)
        self.units.append(unit)
        self.game_area.add_widget(unit)

    def update(self, dt):
        if self.game_over:
            return

        app = App.get_running_app()

        if app.player_role == 'single_player':
            self.bot_update(dt)

        # Разделяем юнитов на две команды
        player_units = [u for u in self.units if u.owner == 'player']
        opponent_units = [u for u in self.units if u.owner == 'opponent']
        player_towers = [t for t in self.towers if t.tower_color == BLUE]
        opponent_towers = [t for t in self.towers if t.tower_color == RED]

        for unit in self.units[:]:
            if unit.hp <= 0:
                self.game_area.remove_widget(unit)
                self.units.remove(unit)
                continue

            # ИЗМЕНЕНИЕ: Передаем в find_target юнитов и башни
            if unit.owner == 'player':
                if not unit.target or unit.target.hp <= 0:
                    unit.find_target(opponent_units, opponent_towers)
            else:  # opponent
                if not unit.target or unit.target.hp <= 0:
                    unit.find_target(player_units, player_towers)

            unit.move(dt)

        is_authoritative = app.player_role in ['host', 'single_player']
        if is_authoritative:
            enemy_king = next((t for t in self.towers if t.tower_name == 'enemy_king'), None)
            if enemy_king and enemy_king.hp <= 0:
                self.end_game("Победа!")
                if app.network:
                    app.network.send({'action': 'game_over', 'message': 'Поражение!'})

            player_king = next((t for t in self.towers if t.tower_name == 'player_king'), None)
            if player_king and player_king.hp <= 0:
                self.end_game("Поражение!")
                if app.network:
                    app.network.send({'action': 'game_over', 'message': 'Победа!'})

    def bot_update(self, dt):
        self.bot_spawn_timer -= dt
        if self.bot_spawn_timer <= 0:
            self.bot_spawn_unit()
            self.bot_spawn_timer = random.uniform(4.0, 7.0)

    def bot_spawn_unit(self):
        unit_name = random.choice(list(UNIT_DATA.keys()))
        spawn_x = random.uniform(50, self.game_area.width - 50)
        spawn_y = random.uniform(self.game_area.height / 2 + 50, self.game_area.height - 100)
        unit = UnitWidget(unit_name, owner='opponent', center=(spawn_x, spawn_y))
        self.units.append(unit)
        self.game_area.add_widget(unit)
        print(f"[BOT] Spawned {unit_name}")

    def update_layout(self, li, size):
        li.canvas.before.clear()
        with li.canvas.before:
            Color(*GREEN)
            Rectangle(pos=(0, 0), size=size)
            Color(*GRAY)
            Line(points=[0, size[1] / 2, size[0], size[1] / 2], width=5)
        if not self.towers:
            self.create_towers()
        self.update_tower_positions(size)

    def end_game(self, message):
        if self.game_over:
            return
        self.game_over = True
        popup_layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        popup_layout.add_widget(Label(text=message, font_size='50sp', bold=True))
        menu_button = Button(text="В меню", size_hint=(1, None), height=60, font_size='24sp')
        menu_button.bind(on_press=self.go_to_menu)
        popup_layout.add_widget(menu_button)
        self.popup = ModalView(size_hint=(0.7, 0.4), auto_dismiss=False)
        self.popup.add_widget(popup_layout)
        self.popup.open()

    def go_to_menu(self, instance):
        self.popup.dismiss()
        self.manager.current = 'game_mode'

    def create_towers(self):
        defs = [{'name': 'enemy_king', 'hp': 2000, 'color': RED}, {'name': 'enemy_left', 'hp': 1000, 'color': RED},
                {'name': 'enemy_right', 'hp': 1000, 'color': RED},
                {'name': 'player_king', 'hp': 2000, 'color': BLUE}, {'name': 'player_left', 'hp': 1000, 'color': BLUE},
                {'name': 'player_right', 'hp': 1000, 'color': BLUE}]
        for d in defs:
            tower = TowerWidget(max_hp=d['hp'], tower_color=d['color'], name=d['name'], size_hint=(None, None))
            self.towers.append(tower)
            self.game_area.add_widget(tower)

    def update_tower_positions(self, s):
        w, h = s
        # Заменяем "магические числа" на именованные константы для ясности
        TOWER_WIDTH = 60
        PRINCESS_TOWER_HEIGHT = 100
        KING_TOWER_HEIGHT = 120
        BOTTOM_MARGIN = 20
        TOP_MARGIN = 20
        SIDE_MARGIN = 40
        SIDE_TOWER_Y_OFFSET = 80 # Дополнительный отступ для боковых башен

        for t in self.towers:
            if t.tower_name == 'enemy_king':
                t.size = (TOWER_WIDTH, KING_TOWER_HEIGHT)
                t.pos = (w / 2 - t.width / 2, h - t.height - TOP_MARGIN)
            elif t.tower_name == 'enemy_left':
                t.size = (TOWER_WIDTH, PRINCESS_TOWER_HEIGHT)
                t.pos = (SIDE_MARGIN, h - t.height - TOP_MARGIN - SIDE_TOWER_Y_OFFSET)
            elif t.tower_name == 'enemy_right':
                t.size = (TOWER_WIDTH, PRINCESS_TOWER_HEIGHT)
                t.pos = (w - t.width - SIDE_MARGIN, h - t.height - TOP_MARGIN - SIDE_TOWER_Y_OFFSET)
            elif t.tower_name == 'player_king':
                t.size = (TOWER_WIDTH, KING_TOWER_HEIGHT)
                t.pos = (w / 2 - t.width / 2, BOTTOM_MARGIN)
            elif t.tower_name == 'player_left':
                t.size = (TOWER_WIDTH, PRINCESS_TOWER_HEIGHT)
                t.pos = (SIDE_MARGIN, BOTTOM_MARGIN + SIDE_TOWER_Y_OFFSET)
            elif t.tower_name == 'player_right':
                t.size = (TOWER_WIDTH, PRINCESS_TOWER_HEIGHT)
                t.pos = (w - t.width - SIDE_MARGIN, BOTTOM_MARGIN + SIDE_TOWER_Y_OFFSET)

    def create_ui(self):
        with self.ui_area.canvas.before:
            Color(*HAND_BG)
            self.ui_bg = Rectangle(pos=self.ui_area.pos, size=self.ui_area.size)
        self.ui_area.bind(pos=self.update_ui_bg, size=self.update_ui_bg)

        self.hand_cards = [
            CardWidget("Рыцарь"),
            CardWidget("Гоблин"),
            CardWidget("Гигант"),
            CardWidget("Лучник")
        ]
        for card in self.hand_cards:
            self.ui_area.add_widget(card)

    def update_ui_bg(self, i, val):
        self.ui_bg.pos = i.pos
        self.ui_bg.size = i.size

    def on_touch_down(self, touch):
        # Если игра окончена или уже выбрана карта, ничего не делаем
        if self.game_over or self.selected_card:
            return super().on_touch_down(touch)

        # Проверяем, было ли нажатие на одну из карт в руке
        if self.ui_area.collide_point(*touch.pos):
            for card in self.hand_cards:
                if card.collide_point(*touch.pos) and not card.disabled:
                    self.selected_card = card
                    # Создаем "призрака" юнита для перетаскивания
                    self.ghost_unit = Label(text=card.unit_name, size_hint=(None, None), size=(40, 40))
                    self.ghost_unit.center = touch.pos
                    self.add_widget(self.ghost_unit)
                    # "Захватываем" событие, чтобы on_touch_move и on_touch_up вызывались для этого виджета
                    touch.grab(self)
                    return True # Мы обработали это событие

        # Если нажатие было не на карту, передаем его дальше (например, кнопкам в popup)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        # Если событие "захвачено" (т.е. мы тащим карту), перемещаем "призрака"
        if touch.grab_current is self:
            self.ghost_unit.center = touch.pos
            return True # Мы обработали это событие
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        # Если мы отпускаем "захваченную" карту
        if touch.grab_current is self:
            # Освобождаем "захват" и убираем "призрака"
            touch.ungrab(self)
            self.remove_widget(self.ghost_unit)
            self.ghost_unit = None

            played_card = self.selected_card
            self.selected_card = None

            # Конвертируем глобальные координаты касания в локальные для игровой зоны
            local_pos = self.game_area.to_local(*touch.pos)
            can_spawn = local_pos[1] < self.game_area.height / 2

            # Если отпустили в своей зоне, спавним юнита
            if self.game_area.collide_point(*local_pos) and can_spawn:
                unit = UnitWidget(played_card.unit_name, owner='player', center=local_pos)
                self.units.append(unit)
                self.game_area.add_widget(unit)

                played_card.set_disabled(True)
                Clock.schedule_once(lambda dt: played_card.set_disabled(False), 5.0)

                app = App.get_running_app()
                if app.network:
                    pos_to_send = (local_pos[0], self.game_area.height - local_pos[1])
                    app.network.send({'action': 'spawn', 'unit': unit.unit_name, 'pos': pos_to_send})
            return True # Мы обработали это событие
        return super().on_touch_up(touch)

class ClashApp(App):
    network = ObjectProperty(None)
    player_role = ''

    def build(self):
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(MainMenuScreen(name='menu'))
        sm.add_widget(GameModeScreen(name='game_mode'))
        sm.add_widget(ConnectScreen(name='connect'))
        sm.add_widget(WaitingScreen(name='waiting'))
        sm.add_widget(GameScreen(name='game'))
        return sm

if __name__ == '__main__':
    ClashApp().run()
