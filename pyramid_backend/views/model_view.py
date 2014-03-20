__author__ = 'tarzan'

from .. import resources as _rsr
from pyramid.view import view_config

class ModelView(object):

    def __init__(self, context, request):
        """
        :type context: pyramid_backend.resources.ModelResource
        :type request: pyramid.request.Request
        """
        self.context = context
        self.request = request

        print context

    @classmethod
    def configure_actions(cls, actions):
        pass

    @property
    def actions(self):
        return []

    @property
    def breadcrumbs(self):
        return []

    def action_list(self):
        return {
            'view': self,
        }

