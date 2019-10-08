"""
The decorators for the event handlers. Usually used as::

    import kopf

    @kopf.on.create('zalando.org', 'v1', 'kopfexamples')
    def creation_handler(**kwargs):
        pass

This module is a part of the framework's public interface.
"""

# TODO: add cluster=True support (different API methods)

from typing import Optional, Callable, Union, Tuple, List

from kopf.reactor import causation
from kopf.reactor import handling
from kopf.reactor import registries
from kopf.structs import bodies

HandlerDecorator = Callable[[registries.HandlerFn], registries.HandlerFn]


def resume(
        group: str, version: str, plural: str,
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.resume()`` handler for the object resuming on operator (re)start. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_cause_handler(
            group=group, version=version, plural=plural,
            reason=None, initial=True, id=id, timeout=timeout,
            fn=fn, labels=labels, annotations=annotations)
        return fn
    return decorator


def create(
        group: str, version: str, plural: str,
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.create()`` handler for the object creation. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_cause_handler(
            group=group, version=version, plural=plural,
            reason=causation.Reason.CREATE, id=id, timeout=timeout,
            fn=fn, labels=labels, annotations=annotations)
        return fn
    return decorator


def update(
        group: str, version: str, plural: str,
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.update()`` handler for the object update or change. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_cause_handler(
            group=group, version=version, plural=plural,
            reason=causation.Reason.UPDATE, id=id, timeout=timeout,
            fn=fn, labels=labels, annotations=annotations)
        return fn
    return decorator


def delete(
        group: str, version: str, plural: str,
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        optional: Optional[bool] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.delete()`` handler for the object deletion. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_cause_handler(
            group=group, version=version, plural=plural,
            reason=causation.Reason.DELETE, id=id, timeout=timeout,
            fn=fn, requires_finalizer=bool(not optional),
            labels=labels, annotations=annotations)
        return fn
    return decorator


def field(
        group: str, version: str, plural: str,
        field: Union[str, List[str], Tuple[str, ...]],
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.field()`` handler for the individual field changes. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_cause_handler(
            group=group, version=version, plural=plural,
            reason=None, field=field, id=id, timeout=timeout,
            fn=fn, labels=labels, annotations=annotations)
        return fn
    return decorator


def event(
        group: str, version: str, plural: str,
        *,
        id: Optional[str] = None,
        registry: Optional[registries.GlobalRegistry] = None,
        labels: Optional[bodies.Labels] = None,
        annotations: Optional[bodies.Annotations] = None,
) -> HandlerDecorator:
    """ ``@kopf.on.event()`` handler for the silent spies on the events. """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else registries.get_default_registry()
        actual_registry.register_event_handler(
            group=group, version=version, plural=plural,
            id=id, fn=fn, labels=labels, annotations=annotations)
        return fn
    return decorator


# TODO: find a better name: `@kopf.on.this` is confusing and does not fully
# TODO: match with the `@kopf.on.{cause}` pattern, where cause is create/update/delete.
def this(
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.SimpleRegistry] = None,
) -> HandlerDecorator:
    """
    ``@kopf.on.this()`` decorator for the dynamically generated sub-handlers.

    Can be used only inside of the handler function.
    It is efficiently a syntax sugar to look like all other handlers::

        @kopf.on.create('zalando.org', 'v1', 'kopfexamples')
        def create(*, spec, **kwargs):

            for task in spec.get('tasks', []):

                @kopf.on.this(id=f'task_{task}')
                def create_task(*, spec, task=task, **kwargs):

                    pass

    In this example, having spec.tasks set to ``[abc, def]``, this will create
    the following handlers: ``create``, ``create/task_abc``, ``create/task_def``.

    The parent handler is not considered as finished if there are unfinished
    sub-handlers left. Since the sub-handlers will be executed in the regular
    reactor and lifecycle, with multiple low-level events (one per iteration),
    the parent handler will also be executed multiple times, and is expected
    to produce the same (or at least predictable) set of sub-handlers.
    In addition, keep its logic idempotent (not failing on the repeated calls).

    Note: ``task=task`` is needed to freeze the closure variable, so that every
    create function will have its own value, not the latest in the for-cycle.
    """
    def decorator(fn: registries.HandlerFn) -> registries.HandlerFn:
        actual_registry = registry if registry is not None else handling.subregistry_var.get()
        actual_registry.register(id=id, fn=fn, timeout=timeout)
        return fn
    return decorator


def register(
        fn: registries.HandlerFn,
        *,
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        registry: Optional[registries.SimpleRegistry] = None,
) -> registries.HandlerFn:
    """
    Register a function as a sub-handler of the currently executed handler.

    Example::

        @kopf.on.create('zalando.org', 'v1', 'kopfexamples')
        def create_it(spec, **kwargs):
            for task in spec.get('tasks', []):

                def create_single_task(task=task, **_):
                    pass

                kopf.register(id=task, fn=create_single_task)

    This is efficiently an equivalent for::

        @kopf.on.create('zalando.org', 'v1', 'kopfexamples')
        def create_it(spec, **kwargs):
            for task in spec.get('tasks', []):

                @kopf.on.this(id=task)
                def create_single_task(task=task, **_):
                    pass
    """
    return this(id=id, timeout=timeout, registry=registry)(fn)
