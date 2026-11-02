from django import template
from categories.services import get_menu_tree

register = template.Library()


@register.inclusion_tag("components/category_chips.html", takes_context=True)
def category_chips(context, active_slug=None):
    return {**context.flatten(), "menu_tree": get_menu_tree(), "active_slug": active_slug}


@register.inclusion_tag("components/category_dropdown.html", takes_context=True)
def category_dropdown(context):
    return {**context.flatten(), "menu_tree": get_menu_tree()}


@register.inclusion_tag("components/category_sidebar.html", takes_context=True)
def category_sidebar(context, category, active_slug=None):
    return {**context.flatten(), "category": category, "active_slug": active_slug}


@register.inclusion_tag("components/category_footer.html", takes_context=True)
def category_footer(context):
    return {**context.flatten(), "menu_tree": get_menu_tree()}