from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    """フォームフィールドにクラスを追加"""
    try:
        return field.as_widget(attrs={"class": css_class})
    except AttributeError:
        # fieldが文字列の場合、エラーを防ぐ
        return field
