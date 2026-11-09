{
    'name': 'Preview Mode',
    'summary': 'See what a button click will do before it does it',
    'version': '20.0.1.0.0',
    'category': 'Productivity',
    'author': 'Samy Mostafa Shaawat',
    'website': 'https://github.com/SamyShaawat/preview_mode',
    'maintainers': ['SamyShaawat'],
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    # PORT: Odoo 20 ACL file; on 16 to 19 use security/ir.model.access.csv (ir.model.access).
    'data': ['security/ir.access.csv'],
    'assets': {
        'web.assets_backend': [
            'preview_mode/static/src/**/*',
        ],
        'web.assets_tests': [
            'preview_mode/static/tests/tours/**/*',
        ],
    },
    'images': ['static/description/popup-confirm.png', 'static/description/popup-create.png'],
    'post_load': 'post_load',
    'installable': True,
    'application': False,
}
