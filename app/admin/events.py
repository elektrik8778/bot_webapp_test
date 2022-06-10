import os
import json
from app import db, Config
from app.admin import bp
from app.models import Place, Placement, Event
from app.admin.forms import PlaceForm, PlacementForm, EventForm
from flask import render_template, request, redirect


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
    placements = Placement.query.filter(Placement.place == event.place).all() if event else []

    if request.method == 'POST':
        if event_form.validate_on_submit():
            eid = int(request.form.get('eid'))
            if eid == 0:
                event = Event()
                db.session.add(event)
            else:
                event: Event = Event.query.get(int(eid))

            event.name = event_form.name.data
            event.description = event_form.description.data
            event.date = request.form.get('date')
            event.time = request.form.get('time')
            event.place = request.form.get('event-place')
            event.placement = request.form.get('event-placement')
            db.session.commit()
            if event_form.poster.data[0]:
                for f in event_form.poster.data:
                    if f.headers['Content-Type'].split('/')[0] in ['video', 'image']:
                        event.add_poster(f)
            return redirect(f'/admin/event/{event.id}')

    return render_template('admin/event.html',
                           event=event,
                           places=places,
                           placements=placements,
                           event_form=event_form)


@bp.get('/admin/event/<eid>/del_poster_file/<filename>')
def del_poster_file(eid, filename):
    Event.query.get(int(eid)).del_poster(filename)
    return redirect(request.referrer)


@bp.post('/admin/get_placemets')
def get_placemets():
    data = json.loads(request.get_data())
    if data['pid']:
        placements = Placement.query.filter(Placement.place == int(data['pid']))
        return json.dumps([p.to_dict() for p in placements])
    else:
        return json.dumps([])
