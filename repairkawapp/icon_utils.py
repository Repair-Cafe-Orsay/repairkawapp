from markupsafe import Markup

# Helper pour rendre une icône de catégorie (Bootstrap Icons uniquement)
# Usage: {{ render_category_icon(category) }}


def render_category_icon(category, with_name: bool = False):
    if not category:
        return ""
    icon = category.icon_name or "question-circle"
    html = f'<i class="bi bi-{icon}"></i>'
    if with_name:
        html += f" {category.name}"
    return Markup(html)
