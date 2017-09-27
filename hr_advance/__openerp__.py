# -*- coding: utf-8 -*-

{
    'name': 'Expense Advance',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Expense Advance Request',
    'description': """
Manage advance for expenses
===========================

    """,
    'author': 'Pambudi Satria',
    'website': 'https://bitbucket.org/pambudisatria/',
    'depends': ['hr_expense', 'report'],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_advance_security.xml',
        'data/hr_advance_data.xml',
        'data/mail_template_data.xml',
        'data/hr_advance_sequence.xml',
        'wizard/hr_advance_refuse_reason.xml',
        'wizard/hr_advance_generate_entries.xml',
        'wizard/hr_expense_generate_entries.xml',
        'views/hr_advance_views.xml',
        'views/hr_expense_views.xml',
        'security/ir_rule.xml',
        'views/report_advance.xml',
        'views/hr_dashboard.xml',
    ],
    'demo': ['data/hr_advance_demo.xml'],
    'installable': True,
}
