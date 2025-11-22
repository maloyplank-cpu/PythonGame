from kivy.app import App
from kivy.uix.button import Button

class MainApp(App):
    """
    Простое Kivy-приложение с одной кнопкой.
    """
    def build(self):
        """
        Этот метод вызывается при запуске приложения
        и должен вернуть корневой виджет.
        """
        # Создаем виджет кнопки
        button = Button(
            text='Нажми меня',
            font_size='20sp',  # Размер шрифта
            on_press=self.on_button_press  # Привязываем функцию к событию нажатия
        )
        return button

    def on_button_press(self, instance):
        """
        Эта функция вызывается при нажатии на кнопку.
        """
        print("Кнопка была нажата!")
        # Меняем текст кнопки, чтобы было видно, что нажатие сработало
        instance.text = 'Нажато!'

if __name__ == '__main__':
    # Запускаем приложение
    MainApp().run()
