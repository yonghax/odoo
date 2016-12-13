from openerp import api, fields, models, _

class MailTemplate(models.Model):
    _inherit = ['mail.template']

    mail_server_id = fields.Many2one(
        'ir.mail_server', 
        'Outgoing Mail Server', 
        readonly=False,
        help="Optional preferred server for outgoing mails. If not set, will be used user configure",
        default=lambda self: self.env.user.mail_server.id
    )

class Message(models.Model):
    _inherit = ['mail.message']

    mail_server_id = fields.Many2one(
        'ir.mail_server', 
        'Outgoing Mail Server', 
        readonly=False,
        help="Optional preferred server for outgoing mails.  If not set, will be used user configure",
        default=lambda self: self.env.user.mail_server.id
    )
    
class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    mail_server_id = fields.Many2one(
        'ir.mail_server', 
        'Outgoing Mail Server', 
        readonly=False,
        help="Optional preferred server for outgoing mails.  If not set, will be used user configure",
        default=lambda self: self.env.user.mail_server.id
    )