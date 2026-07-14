# VNP physical probe

The probe generates an Ed25519 keypair on the node at first start. The private
key is stored only in the mounted `NODE_KEY_DIR` volume with mode `0600`; the
probe never sends or prints it. Registration reads only `public_key` and
`key_id` over the authenticated deployment channel.

The initial target set is deliberately limited to real, public Veklom health
endpoints:

- `https://vnp.veklom.com/health`
- `https://api.veklom.com/health`
- `https://cappo.veklom.com/health`

These endpoints are measured for transport timing and a status/JSON semantic
assertion. They are not score inputs until a later measurement-window change.
