#!/usr/bin/env python3


from os import environ
import logging
import logging.handlers

from flask import Flask, jsonify
import psycopg2


def create_app():
    app = Flask(__name__)
    app.config.from_json(environ['APP_CONFIG'])
    if not app.debug:
        stream_handler = logging.handlers.SysLogHandler(address='/dev/log')
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
    return app


app = create_app()


@app.route('/api/v1/objects/hosts')
def hosts():
    conn = psycopg2.connect(
        dbname=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASS'],
    )
    cur = conn.cursor()
    cur.execute(
        '''
        select
            icinga_objects.name1,
            icinga_hoststatus.current_state,
            icinga_hoststatus.scheduled_downtime_depth,
            icinga_hoststatus.state_type,
            icinga_hoststatus.output,
            icinga_hoststatus.long_output
        from icinga_objects
        left join icinga_hoststatus on icinga_objects.object_id = icinga_hoststatus.host_object_id
        where
            icinga_objects.objecttype_id = 1 and
            icinga_objects.is_active = 1
        ;
        ''',
    )

    results = []
    for host_name, state, downtime_depth, state_type, output, long_output in cur.fetchall():
        results.append({
            'type': 'Host',
            'attrs': {
                'display_name': host_name,
                'downtime_depth': downtime_depth,
                'state': state,
                'state_type': state_type,
                'last_check_result': {
                    'output': output + '\n' + long_output.replace('\\n', '\n'),
                },
            },
        })

    cur.close()
    conn.close()

    return jsonify({'results': results})


@app.route('/api/v1/objects/services')
def services():
    conn = psycopg2.connect(
        dbname=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASS'],
    )
    cur = conn.cursor()
    cur.execute(
        '''
        select
            icinga_objects.name1,
            icinga_objects.name2,
            icinga_servicestatus.current_state,
            icinga_servicestatus.scheduled_downtime_depth,
            icinga_servicestatus.state_type,
            icinga_servicestatus.output,
            icinga_servicestatus.long_output
        from icinga_objects
        left join icinga_servicestatus on icinga_objects.object_id = icinga_servicestatus.service_object_id
        where
            icinga_objects.objecttype_id = 2 and
            icinga_objects.is_active = 1
        ;
        ''',
    )

    results = []
    for host_name, service_name, state, downtime_depth, state_type, output, long_output in cur.fetchall():
        results.append({
            'type': 'Service',
            'attrs': {
                'host_name': host_name,
                'display_name': service_name,
                'downtime_depth': downtime_depth,
                'state': state,
                'state_type': state_type,
                'last_check_result': {
                    'output': output + '\n' + long_output.replace('\\n', '\n'),
                },
            },
        })

    cur.close()
    conn.close()

    return jsonify({'results': results})


if __name__ == '__main__':
    app.run(host='::')
