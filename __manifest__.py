{
    'name': 'Preview Mode',
    'summary': 'See what a button click will do before it does it',
    'version': '20.0.1.0.0',
    'category': 'Productivity',
    'author': 'Samy Mostafa Shaawat',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    # PORT: Odoo 20 ACL file; on 16 to 19 use security/ir.model.access.csv (ir.model.access).
    'data': ['security/ir.access.csv'],
    'assets': {
        'web.assets_backend': [
            'preview_mode/static/src/**/*',
        ],
    },
    'post_load': 'post_load',
    'installable': True,
    'application': False,
}
