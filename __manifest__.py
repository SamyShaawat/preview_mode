{
    'name': 'Preview Mode',
    'summary': 'See what a button click will do before it does it',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'author': 'Samy Mostafa Shaawat',
    'license': 'OPL-1',
    'depends': ['base', 'web'],
    # PORT: Odoo 20 has one ACL file with a domain; 16 to 19 use ir.model.access + an ir.rule.
    'data': ['security/ir.model.access.csv', 'security/preview_mode_security.xml'],
    'assets': {
        'web.assets_backend': [
            'preview_mode/static/src/**/*',
        ],
    },
    'post_load': 'post_load',
    'installable': True,
    'application': False,
}
