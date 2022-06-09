import os
import json
from app import db, Config
from app.admin import bp
from app.models import Place, Placement, Event
from app.admin.forms import PlaceForm, PlacementForm, EventForm
from flask import render_template, request, redirect
from werkzeug.utils import secure_filename


@bp.get('/admin/events')
def events_view():
    events = Event.query.all()
    return render_template('admin/events.html', events=events)


@bp.post('/admin/event/<eid>')
@bp.get('/admin/event/<eid>')
def event_view(eid):
    event = Event.query.get(int(eid))
    event_form = EventForm()
    places = Place.query.all()

    if request.method == 'POST':
        if event_form.validate_on_submit():
            # eid = int(request.form.get('eid'))
            # if eid == 0:
            #     event = Event()
            #     db.session.add(event)
            # else:
            #     event: Event = Event.query.get(int(eid))
            #
            # event.name = event_form.name.data
            # event.description = event_form.description.data
            # event.date = request.form.get('date')
            # event.time = request.form.get('time')
            # event.place = request.form.get('event-place')
            # event.placement = request.form.get('event-placement')
            # db.session.commit()
            if event_form.poster.data[0]:
                for f in event_form.poster.data:
                    filename = secure_filename(f.filename)
                    if f.headers['Content-Type'].split('/') in ['video', 'image']:
                        print(f.__dict__)
            return redirect(f'/admin/place/{event.id}')


    #     elif placement_form.validate_on_submit() and placement_form.save_placement.data:
    #         uploaded_file = placement_form.excel_file.data
    #         filename = secure_filename(uploaded_file.filename)
    #         placement = Placement()
    #         placement.place = place.id
    #         placement.name = placement_form.name.data
    #         placement.excel_filename = filename
    #         db.session.add(placement)
    #         db.session.commit()
    #         placement_catalog = os.path.join(os.path.join(Config.UPLOAD_FOLDER, 'placements', str(placement.id)))
    #         if not os.path.exists(placement_catalog):
    #             os.makedirs(placement_catalog)
    #         uploaded_file.save(os.path.join(placement_catalog, filename))
    #         placement.placement = create_placement(placement_catalog, filename)
    #         db.session.commit()
    #         return redirect(request.referrer)
    #
    return render_template('admin/event.html',
                           event=event,
                           places=places,
                           event_form=event_form)


@bp.post('/admin/get_placemets')
def get_placemets():
    data = json.loads(request.get_data())
    if data['pid']:
        placements = Placement.query.filter(Placement.place == int(data['pid']))
        return json.dumps([p.to_dict() for p in placements])
    else:
        return json.dumps([])
