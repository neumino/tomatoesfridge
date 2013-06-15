import cherrypy
from flask import Flask, request, send_from_directory
import rethinkdb as r
import json
import requests
import configparser

app = Flask(__name__)
app.debug = True

API_KEY = None

@app.route("/init")
def get_init_movie():
    try:
        id_movie = request.args.get('id_movie', '')
    except ValueError:
        answer = {"error": "id_movie could not be converted to a number"}
        return json.dumps(answer)
    else:
        result = r.table("movie").get(id_movie).run()

        if result is None:
            # Fetch similar movies from Rotten Tomatoes and save it
            print "Init movie: Fetching data from Rotten tomatoes"
            url = "http://api.rottentomatoes.com/api/public/v1.0/movies/"+str(id_movie)+".json"
            http_answer = do_http_request(url, None)
            if "id" in http_answer: # If id is defined, we have a valid object
                r.table("movie").insert( http_answer ).run( noreply=True)
                return json.dumps(http_answer)
            else:
                answer = {"error": "Movie not found. API rate limit reached?"}
                return json.dumps(answer)
        else:
            print 'Init movie: cached'
            return json.dumps(result)


@app.route("/get")
def get_movie():
    try:
        id_movie = request.args.get('id_movie', '')
    except ValueError:
        answer = {"error": "id_movie could not be converted to a number"}
        return json.dumps(answer)
    else:
        result = r.table("movie").get(id_movie).do(lambda movie:
            r.branch( (movie != None) & (movie.has_fields("similar_movies_id")),
                r.expr({"id":id_movie}).merge({"movies":movie["similar_movies_id"].map(lambda similar_movie_id:
                    r.table("movie").get(similar_movie_id)
                )}),
                None
            )).run()

        if result is None:
            # Fetch similar movies from Rotten Tomatoes and save it
            print "Get movie: Fetching data from Rotten tomatoes"
            url = "http://api.rottentomatoes.com/api/public/v1.0/movies/"+str(id_movie)+"/similar.json?apikey="+API_KEY
            http_answer = do_http_request(url, None)
            if "movies" in http_answer:
                r.table("movie").insert( http_answer["movies"] ).run( noreply=True)
                similar_movies_id = map(get_id, http_answer["movies"])
                result = r.table("movie").get(id_movie).update({"similar_movies_id": similar_movies_id }).run( noreply=True)
                http_answer['id'] = id_movie
                return json.dumps(http_answer)
            else:
                answer = {"error": "No similar movies returned. API rate limit reached?"}
                return json.dumps(answer)
        else:
            print "Get movie: cached"
            return json.dumps(result)


@app.route("/search")
def search():
    if not "search_input" in request.form:
        answer = {"error": "No keywords provided"}
        return json.dumps(answer)

    search_input = request.form['search_input']
 
    url = "http://api.rottentomatoes.com/api/public/v1.0/movies.json"
    values = {
        "q" : search_input,
        "page": 1,
        "page_limit": 10
        }
    http_answer = do_http_request(url, values)


    if movies in content_json:
        # If the movie is already saved, we are just going to skip it.
        r.table("movie").insert(content_json["movies"]).run( noreply=True )
        return content_json["movies"]
    else:
        return "[]"

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return send_from_directory('../web/', path)

def get_id(movie):
    return movie["id"]

def do_http_request(url, values):
    # Send HTTP POST request
    if values == None:
        values = {}
    values["apikey"] = API_KEY

    response = requests.get(url, params=values)
    return response.json()

def load_conf():
    global API_KEY
    config = configparser.ConfigParser()
    config.read('apikey.conf')
    API_KEY = config['DEFAULT']["API_KEY"]


def init_database():
    r.connect(db="tomatoesfridge").repl()

    try:
        r.db_create("tomatoesfridge").run()
    except r.errors.RqlRuntimeError as e:
        print "Database `tomatoesfridge` not created."
        print str(e)
    else:
        print "Database `tomatoesfridge` created"

    try:
        r.table_create("movie").run()
    except r.errors.RqlRuntimeError as e:
        print "Table `movie` in `tomatoesfridge` not created."
        print str(e)
    else:
        print "Table `movie` in `tomatoesfridge` created"


if __name__ == "__main__":
    load_conf()
    init_database()
    #app.run(host='0.0.0.0', port=3000)

    cherrypy.tree.graft(app, '/')
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 4000,
        })
    cherrypy.engine.start()
    cherrypy.engine.block()
