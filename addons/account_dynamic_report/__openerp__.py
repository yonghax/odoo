{
    'name': 'Dynamic Financial Accounting Reports',
    'version': '1.0',
    'category': 'Accounting',
    'author': 'Yohanes Ho',
    'summary': 'Dynamic Financial Accounting Report',
    'description': """
Dynamic Financial Accounting Reports.
====================================

This module adds two new reports:
* Configuration Financial Report Template
* Replace Odoo Standard Financial Report
    """,
    'author': 'Yohanes Ho',
    'depends': ['account'],
    'data': [
        #'wizard/account_report_print_journal_view.xml',
        #'views/report_journal.xml',
        #'wizard/account_report_partner_ledger_view.xml',
        'views/account_dynamic_financial_report_view.xml',
        'data/account_type_data.xml',
        'report/financial_report.xml',
    ],
    'demo': [],
    'installable': True,
}