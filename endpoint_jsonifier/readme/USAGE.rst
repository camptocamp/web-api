This module by itself contains no business logic, but its configuration can be used to
manage endpoints' data export.

For example:

.. code-block:: python

    parser = endpoint.export_id.get_json_parser()
    prod_domain = [("sale_ok", "=", True)]
    prod_data = [p.jsonify(parser) for p in env["product.product"].search(prod_domain)]
    resp = Response(json.dumps(prod_data), content_type="application/json", status=200)
    result = dict(response=resp)
