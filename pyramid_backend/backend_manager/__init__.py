import six

__author__ = 'tarzan'
import re
import inspect
import itertools
from collections import OrderedDict
from pyramid.decorator import reify

_managers_factory = []


def _name_to_underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _name_to_words(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    words = re.split('[_\s]+', name)

    return ' '.join([w.title() for w in words])


def create_backend_manager(model):
    """
    create backend manager for a model
    :rtype Manager
    """
    for mf in _managers_factory:
        mgr = mf(model)
        if mgr:
            return mgr

    raise NotImplementedError('Can not find backend manager for model "%s"' % model.__name__)


def register_manager_factory(factory):
    global _managers_factory
    _managers_factory.append(factory)


def get_manager(model):
    """
    get backend manager for a model
    :rtype Manager
    """
    try:
        return model.__backend_manager__
    except AttributeError:
        manager = create_backend_manager(model)
        model.__backend_manager__ = manager
        return manager


class AttrDisplayConf(object):
    def __init__(self, attr_name, *args):
        self.attr_name = attr_name

        def first_instance(types, default):
            for arg in args:
                if isinstance(arg, types):
                    return arg
            return default

        self.label = first_instance(six.string_types, _name_to_words(attr_name))
        self.limit = first_instance(six.integer_types, 5)

    def values(self, obj):
        vals = self.value(obj)
        try:
            vals = itertools.islice(vals, self.limit)
        except TypeError:
            vals = [vals, ]
        return vals

    def value(self, obj):
        return obj.__getattribute__(self.attr_name)


class Manager(object):

    __attr_display_conf_class__ = AttrDisplayConf

    def __init__(self, model):
        """
        :type model: class
        """
        assert inspect.isclass(model)
        self.Model = model
        self.actions = OrderedDict()

    @property
    def column_names(self):
        return dir(self.Model)

    @reify
    def default_actions(self):
        return OrderedDict([
            ('list', {
                'route_name': 'admin_site',
                'context': self.ModelResource,
                'name': '',
                'attr': 'action_list',
                'renderer': 'pyramid_backend:templates/list.mak',
                'permission': 'list',
                '_icon': 'list',
                '_label': self.display_name + u' list',
            }),
            ('create', {
                'route_name': 'admin_site',
                'context': self.ModelResource,
                'name': 'create',
                'attr': 'action_create',
                'renderer': 'pyramid_backend:templates/create.mak',
                'permission': 'create',
                '_icon': 'plus',
                '_label': u'Create new ' + self.display_name,
            }),
            ('detail', {
                'route_name': 'admin_site',
                'context': self.ObjectResource,
                'name': '',
                'attr': 'action_detail',
                'renderer': 'pyramid_backend:templates/detail.mak',
                'permission': 'detail',
                '_icon': 'eye-open',
                '_label': u'View %s detail',
            }),
            ('update', {
                'route_name': 'admin_site',
                'context': self.ObjectResource,
                'name': 'update',
                'attr': 'action_update',
                'renderer': 'pyramid_backend:templates/update.mak',
                'permission': 'update',
                '_icon': 'pencil',
                '_label': u'Update %s',
            }),
            ('delete', {
                'route_name': 'admin_site',
                'context': self.ObjectResource,
                'name': 'delete',
                'attr': 'action_delete',
                'renderer': 'pyramid_backend:templates/update.mak',
                'permission': 'delete',
                '_icon': 'remove',
                '_label': u'Delete %s',
                '_onclick': u"return confirm('Do you want to delete %s?');",
            }),
        ]
        )

    _configurable_properties = [
        'slug',
        '__acl__',
        'display_name',
        'schema_cls',
        'id_attr',
        'list__columns_to_display',
        'detail__columns_to_display',
        'list__items_per_page',
        'detail__relations_to_display',
    ]

    _display_config = [
        'list__columns_to_display',
        'detail__columns_to_display',
        'detail__relations_to_display',
    ]

    def _make_attr_display_config(self, conf):
        if not isinstance(conf, (list, tuple)):
            conf = [conf, ]
        return self.__attr_display_conf_class__(*conf)

    def __getattribute__(self, name):
        if name in Manager._configurable_properties:
            try:
                val = getattr(self.Model, '__backend_' + name + '__')
            except AttributeError:
                val = getattr(self, '__default_' + name + '__')
            if name in Manager._display_config:
                val = [self._make_attr_display_config(v) for v in val]
            if name == 'id_attr':
                if not isinstance(val, (list, tuple)):
                    val = (val, )
            setattr(self, name, val)
            return val
        return super(Manager, self).__getattribute__(name)

    __default_schema_cls__ = None
    __default_id_attr__ = 'id'
    __default_list__items_per_page__ = 50

    @property
    def __default_slug__(self):
        return _name_to_underscore(self.Model.__name__)

    @property
    def __default_display_name__(self):
        return _name_to_words(self.Model.__name__)

    @property
    def __default_list__columns_to_display__(self):
        return OrderedDict(zip(
            self.column_names,
            [_name_to_words(n) for n in self.column_names]
        ))

    @property
    def __default_detail__columns_to_display__(self):
        return self.__default_list__columns_to_display__

    @property
    def __default_detail__relations_to_display__(self):
        return {}

    @reify
    def ModelResource(self):
        from pyramid_backend import resources

        return resources.model_resource_class(self.Model)

    @reify
    def ObjectResource(self):
        from pyramid_backend import resources

        return resources.object_resource_class(self.Model)

    def get_id_filters(self, id_value):
        id_part_count = len(self.id_attr)
        vals = str(id_value).split('-', id_part_count)
        return dict(zip(self.id_attr, vals))

    def normalize_action(self, action_conf):
        assert bool(action_conf), 'Can not be empty configuration'
        if not isinstance(action_conf, (list, tuple,)):
            assert action_conf in self.default_actions, 'Unknown action named "%s"' % action_conf
            action_conf = (action_conf, self.default_actions[action_conf])
        return action_conf

    def add_action(self, action_conf):
        action_name, action_conf = self.normalize_action(action_conf)
        self.actions[action_name] = action_conf
        return action_name, action_conf

    def object_id(self, obj):
        return u'-'.join([six.text_type(getattr(obj, attr_name)) for attr_name in self.id_attr])

    def create(self, data):
        raise NotImplementedError()

    def update(self, obj, data):
        raise NotImplementedError()

    def fetch_objects(self, filters, fulltext=True, page=1):
        raise NotImplementedError()

    def count_objects(self, filters):
        raise NotImplementedError()

    def find_object(self, id_value):
        id_filters = self.get_id_filters(id_value)
        objs = list(self.fetch_objects(id_filters, fulltext=False))
        return objs[0] if objs else None
