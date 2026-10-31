"""Lambda entry point of the Ingest function (handler: ingest.handler.handler)."""

from mangum import Mangum

import composition
import logs

logs.configure()
# Built at cold start, so a broken configuration fails the deploy's first call loudly.
handler = Mangum(composition.ingest_app(), lifespan="off")
