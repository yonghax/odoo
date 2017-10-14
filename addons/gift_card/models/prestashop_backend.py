# -*- coding: utf-8 -*-

from openerp import models, fields, api, _

class PrestshopBackend(models.Model):
    _inherit = 'prestashop.backend'
    import_gift_card_since	= fields.Datetime(
        string='Import Gift Card Since',
    )