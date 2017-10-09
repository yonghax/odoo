from openerp import api, fields, models, _
# import logging
# _logger = logging.getLogger(__name__)

class HrEquipment(models.Model):
    
    _inherit = ['hr.equipment']
    
    location_id = fields.Many2one(string=u'Location',comodel_name='hr.equipment.location')

class EquipmentBranch(models.Model):
    _name = 'hr.equipment.branch'

    code = fields.Char(string='Code')
    name = fields.Char(string=u'Name')
    active = fields.Boolean(string=u'Active',default=True,)
    partner_id = fields.Many2one(string=u'Address', comodel_name='res.partner', domain="[('parent_id','=',1)]",)
    location_ids = fields.One2many(
        string=u'Locations',
        comodel_name='hr.equipment.location',
        inverse_name='branch_id',
    )
    

class EquipmentLocation(models.Model):
    _name = 'hr.equipment.location'
    
    code = fields.Char(string=u'Code',)
    name = fields.Char(string=u'Name',)
    active = fields.Boolean(string=u'Active',default=True,)
    branch_id = fields.Many2one(string=u'Branch',comodel_name='hr.equipment.branch',ondelete='cascade',)
    equipment_ids = fields.One2many(string=u'Equipments',comodel_name='hr.equipment',inverse_name='location_id',)

class EquipmentHistory(models.Model):
    _name = 'hr.equipment.history'
    