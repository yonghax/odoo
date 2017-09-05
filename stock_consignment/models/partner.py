# -*- coding: utf-8 -*-

from openerp import models, fields, api

class res_partner(models.Model):
    _inherit = 'res.partner'

    is_tax_payable = fields.Boolean(string='Is Tax Payor')
    tax_id_number = fields.Char(string='Tax ID Number')
    default_purchase_tax = fields.Many2one(
        string='Default Tax',
        comodel_name='account.tax',
        domain=[('type_tax_use', '=', 'purchase')],
        ondelete='cascade',
        auto_join=False
    )

    @api.onchange('is_tax_payable')
    def _resetTaxInfo(self):
        if not self.is_tax_payable:
            self.tax_id_number = False 
            self.default_purchase_tax = False