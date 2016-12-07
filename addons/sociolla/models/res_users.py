from openerp import api, fields, models, _, SUPERUSER_ID

class res_users(models.Model):
    
    _inherit = ['res.users']
    
    esignature = fields.Binary(
        string='e-Signature',
        attachment=True,
        help="This field holds the image used as image for the product, limited to 256x256px."
    )
    
    