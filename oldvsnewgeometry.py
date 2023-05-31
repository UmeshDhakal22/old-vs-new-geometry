#importing all the requirements
import requests
import json
import pandas as pd
import geojson
import html

#Initializing both the api endpoints 
osmcha_base_url = "https://osmcha.org/api/v1/changesets/"
changeset_base_url="https://s3.amazonaws.com/mapbox/real-changesets/production"

#assigning query parameter and token of OSMcha to variables
#give your own query parameter and token id
kathmandu="page=1&page_size=1000&date__gte=2023-05-15&date__lte=2023-05-25&geometry=%7B%22type%22%3A%22Polygon%22%2C%22coordinates%22%3A%5B%5B%5B85.188235%2C27.681436%5D%2C%5B85.231539%2C27.652482%5D%2C%5B85.222017%2C27.629166%5D%2C%5B85.240128%2C27.580375%5D%2C%5B85.266427%2C27.570175%5D%2C%5B85.294522%2C27.603775%5D%2C%5B85.28236%2C27.644198%5D%2C%5B85.303252%2C27.692226%5D%2C%5B85.351794%2C27.667949%5D%2C%5B85.421414%2C27.724067%5D%2C%5B85.524809%2C27.725472%5D%2C%5B85.538154%2C27.754919%5D%2C%5B85.565476%2C27.764509%5D%2C%5B85.531477%2C27.792586%5D%2C%5B85.473174%2C27.778142%5D%2C%5B85.450199%2C27.817911%5D%2C%5B85.298667%2C27.812433%5D%2C%5B85.251658%2C27.775176%5D%2C%5B85.26749%2C27.746075%5D%2C%5B85.214604%2C27.73766%5D%2C%5B85.222193%2C27.728295%5D%2C%5B85.19801%2C27.71694%5D%2C%5B85.188235%2C27.681436%5D%5D%5D%7D"
headers = {"Authorization": "Token token_id"}

#getting the response from the first api endpoint
response = requests.get(f"{osmcha_base_url}?{kathmandu}", headers=headers)
osmcha_data= response.json()

#initializing empty lists
changes=[]
ids=[]

#getting all the changesets with tag highway=primary from first api endpoint
for item in osmcha_data['features']:
  try:
    if ('primary' in item['properties']['tag_changes']['highway']):
        ids.append(item['id'])
        changes.append(item)
  except:
    pass

#Getting all the changes needed from second API endpoint
changes_list = []
openstreeturl="https://www.openstreetmap.org/{}/{}"
for feature in changes:
    changeset_id = str(feature['id'])
    changeset_url = f"{changeset_base_url}/{changeset_id}.json"
    date = feature['properties']['date']

    response = requests.get(changeset_url)
    changeset_data = response.json()

    for x in changeset_data['elements']:
        new_geometry = []
        old_geometry = []
        if x['changeset'] == changeset_id:
            feature_id = x['id']
            if 'old' in x:
                old_tags = x['old']['tags']
            else:
                old_tags = "-"

            if 'name:en' in x['tags']:
                name_value = x['tags']['name:en']
            else:
                name_value = "-"

            if 'type' in x and x['type'] == 'node':
                continue

            try:
                n_tags = x['tags']
            except:
                n_tags = "-"

            coordinates = []
            old_coordinates = []
            if 'nodes' in x:
                for node in x["nodes"]:
                    coordinates.append((float(node["lon"]), float(node["lat"])))

            if 'old' in x and 'nodes' in x['old']:
                for node in x['old']["nodes"]:
                    old_coordinates.append((float(node["lon"]), float(node["lat"])))

            geometry = geojson.LineString(coordinates) if x["type"] == "way" else geojson.Polygon([coordinates])
            feature_geojson = geojson.Feature(geometry=geometry, properties={})
            new_geometry.append(feature_geojson)

            geometry_1 = geojson.LineString(old_coordinates) if x["type"] == "way" else geojson.Polygon([old_coordinates])
            feature_geojson = geojson.Feature(geometry=geometry_1, properties={})
            old_geometry.append(feature_geojson)
            geometry_changed = "No"
            if coordinates != old_coordinates:
                geometry_changed = "Yes"


            if 'highway' in old_tags and old_tags['highway'] == 'primary':
                changes = {
                    'changeset_id': x['changeset'],
                    'feature_id': feature_id,
                    'user': x['user'],
                    'user_id': x['uid'],
                    'action': x['action'],
                    'type': x.get('type', ''),
                    'old_tags': old_tags,
                    'new_tags': n_tags,
                    'date': date,
                    'name': name_value,
                    'geometry_changed': geometry_changed,
                    'viewOSM': openstreeturl.format(html.escape(x['type']), feature_id)
                }
                if geometry_changed == "Yes":
                    changes['new_geometry'] = new_geometry
                    changes['old_geometry'] = old_geometry
                else:
                    changes['new_geometry'] = new_geometry
                changes_list.append(changes)

            elif 'highway' in n_tags and n_tags['highway'] == 'primary':
                changes = {
                    'changeset_id': x['changeset'],
                    'feature_id': feature_id,
                    'user': x['user'],
                    'user_id': x['uid'],
                    'action': x['action'],
                    'type': x.get('type', ''),
                    'old_tags': old_tags,
                    'new_tags': n_tags,
                    'date': date,
                    'name': name_value,
                    'geometry_changed': geometry_changed,
                    'viewOSM': openstreeturl.format(html.escape(x['type']), feature_id)
                }
                if geometry_changed == "Yes":
                    changes['new_geometry'] = new_geometry
                    changes['old_geometry'] = old_geometry
                else:
                    changes['new_geometry'] = new_geometry
                    changes['old_geometry'] = '-'
                changes_list.append(changes)


#Creating dataframe from the changes
df=pd.DataFrame(changes_list)


#adding three new columns that checks for the kind of changes made in tags
df['tags_added'] = ""
df['tags_removed'] = ""
df['tags_modified'] = ""

for i, row in df.iterrows():
    old_tags = row['old_tags']
    new_tags = row['new_tags']
    
    tags_added = {}
    tags_removed = {}
    tags_modified = {}

    for key, value in new_tags.items():
        if key not in old_tags:
            tags_added[key] = value
        elif old_tags[key] != value:
            tags_modified[key] = {'old': old_tags[key], 'new': value}

    for key, value in old_tags.items():
        if key not in new_tags:
            tags_removed[key] = value
    
    if not tags_added:
        tags_added = '-'
    if not tags_removed:
        tags_removed = '-'
    if not tags_modified:
        tags_modified = '-'

    df.at[i, 'tags_added'] = tags_added
    df.at[i, 'tags_removed'] = tags_removed
    df.at[i, 'tags_modified'] = tags_modified

df['tags_added'] = df['tags_added'].astype(str)
df['tags_removed'] = df['tags_removed'].astype(str)
df['tags_modified'] = df['tags_modified'].astype(str)


#Ordering the columns as per need
desired_order = ['feature_id', 'name', 'type', 'action','tags_added','tags_removed','tags_modified','changeset_id','date','user','user_id','new_tags','old_tags','geometry_changed','new_geometry','old_geometry','viewOSM']
df = df.reindex(columns=desired_order)
df.set_index('feature_id', inplace=True)

#Getting output in the form of csv file
df.to_csv('nodes.csv')