import asyncio
import copy
import datetime
import logging

import pykube
import requests

from kopf import config
from kopf.clients import auth
from kopf.structs import bodies

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 1024
CUT_MESSAGE_INFIX = '...'


async def post_event(
        *,
        ref: bodies.ObjectReference,
        type: str,
        reason: str,
        message: str = '',
) -> None:
    """
    Issue an event for the object.

    This is where they can also be accumulated, aggregated, grouped,
    and where the rate-limits should be maintained. It can (and should)
    be done by the client library, as it is done in the Go client.
    """
    now = datetime.datetime.utcnow()

    # See #164. For cluster-scoped objects, use the current namespace from the current context.
    # It could be "default", but in some systems, we are limited to one specific namespace only.
    namespace: str = ref.get('namespace') or auth.get_pykube_cfg().namespace
    full_ref: bodies.ObjectReference = copy.copy(ref)
    full_ref['namespace'] = namespace

    # Prevent a common case of event posting errors but shortening the message.
    if len(message) > MAX_MESSAGE_LENGTH:
        infix = CUT_MESSAGE_INFIX
        prefix = message[:MAX_MESSAGE_LENGTH // 2 - (len(infix) // 2)]
        suffix = message[-MAX_MESSAGE_LENGTH // 2 + (len(infix) - len(infix) // 2):]
        message = f'{prefix}{infix}{suffix}'

    body = {
        'metadata': {
            'namespace': namespace,
            'generateName': 'kopf-event-',
        },

        'action': 'Action?',
        'type': type,
        'reason': reason,
        'message': message,

        'reportingComponent': 'kopf',
        'reportingInstance': 'dev',
        'source': {'component': 'kopf'},  # used in the "From" column in `kubectl describe`.

        'involvedObject': full_ref,

        # format: '2019-01-28T18:25:03.000000Z'
        'firstTimestamp': now.isoformat() + 'Z',  # seen in `kubectl describe`
        'lastTimestamp': now.isoformat() + 'Z',  # seen in `kubectl get events`
        'eventTime': now.isoformat() + 'Z',
    }

    try:
        api = auth.get_pykube_api()
        obj = pykube.Event(api, body)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(config.WorkersConfig.get_syn_executor(), obj.create)

    except (requests.exceptions.HTTPError, pykube.exceptions.HTTPError) as e:
        # Events are helpful but auxiliary, they should not fail the handling cycle.
        # Yet we want to notice that something went wrong (in logs).
        logger.warning("Failed to post an event. Ignoring and continuing. "
                       f"Error: {e!r}. "
                       f"Event: type={type!r}, reason={reason!r}, message={message!r}.")
