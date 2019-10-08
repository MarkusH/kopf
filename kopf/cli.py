import asyncio
import functools
from typing import Any, Optional, Callable, List

import click

from kopf import config
from kopf.clients import auth
from kopf.engines import peering
from kopf.reactor import running
from kopf.utilities import loaders


def cli_login() -> None:
    try:
        auth.login(verify=True)
    except auth.LoginError as e:
        raise click.ClickException(str(e))
    except auth.AccessError as e:
        raise click.ClickException(str(e))


def logging_options(fn: Callable[..., Any]) -> Callable[..., Any]:
    """ A decorator to configure logging in all command in the same way."""
    @click.option('-v', '--verbose', is_flag=True)
    @click.option('-d', '--debug', is_flag=True)
    @click.option('-q', '--quiet', is_flag=True)
    @functools.wraps(fn)  # to preserve other opts/args
    def wrapper(verbose: bool, quiet: bool, debug: bool, *args: Any, **kwargs: Any) -> Any:
        config.configure(debug=debug, verbose=verbose, quiet=quiet)
        return fn(*args, **kwargs)

    return wrapper


@click.version_option(prog_name='kopf')
@click.group(name='kopf', context_settings=dict(
    auto_envvar_prefix='KOPF',
))
def main() -> None:
    pass


@main.command()
@logging_options
@click.option('-n', '--namespace', default=None)
@click.option('--standalone', is_flag=True, default=False)
@click.option('--dev', 'priority', type=int, is_flag=True, flag_value=666)
@click.option('-P', '--peering', 'peering_name', type=str, default=None, envvar='KOPF_RUN_PEERING')
@click.option('-p', '--priority', type=int, default=0)
@click.option('-m', '--module', 'modules', multiple=True)
@click.argument('paths', nargs=-1)
def run(
        paths: List[str],
        modules: List[str],
        peering_name: Optional[str],
        priority: int,
        standalone: bool,
        namespace: Optional[str],
) -> None:
    """ Start an operator process and handle all the requests. """
    cli_login()
    loaders.preload(
        paths=paths,
        modules=modules,
    )
    return running.run(
        standalone=standalone,
        namespace=namespace,
        priority=priority,
        peering_name=peering_name,
    )


@main.command()
@logging_options
@click.option('-n', '--namespace', default=None)
@click.option('-i', '--id', type=str, default=None)
@click.option('--dev', 'priority', flag_value=666)
@click.option('-P', '--peering', 'peering_name', required=True, envvar='KOPF_FREEZE_PEERING')
@click.option('-p', '--priority', type=int, default=100, required=True)
@click.option('-t', '--lifetime', type=int, required=True)
@click.option('-m', '--message', type=str)
def freeze(
        id: Optional[str],
        message: Optional[str],  # pylint: disable=unused-argument
        lifetime: int,
        namespace: Optional[str],
        peering_name: str,
        priority: int,
) -> None:
    """ Freeze the resource handling in the cluster. """
    cli_login()
    ourserlves = peering.Peer(
        id=id or peering.detect_own_id(),
        name=peering_name,
        namespace=namespace,
        priority=priority,
        lifetime=lifetime,
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ourserlves.keepalive())


@main.command()
@logging_options
@click.option('-n', '--namespace', default=None)
@click.option('-i', '--id', type=str, default=None)
@click.option('-P', '--peering', 'peering_name', required=True, envvar='KOPF_RESUME_PEERING')
def resume(
        id: Optional[str],
        namespace: Optional[str],
        peering_name: str,
) -> None:
    """ Resume the resource handling in the cluster. """
    cli_login()
    ourselves = peering.Peer(
        id=id or peering.detect_own_id(),
        name=peering_name,
        namespace=namespace,
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ourselves.disappear())
