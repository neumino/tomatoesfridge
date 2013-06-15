import cherrypy
from flask import Flask, request, send_from_directory, g, abort
import rethinkdb as r
import json
import requests
import configparser
from rethinkdb.errors import RqlRuntimeError, RqlDriverError


app = Flask(__name__)


API_KEY = None

# We use one connection per request
@app.before_request
def before_request():
    try:
        g.rdb_conn = r.connect(host=RDB_HOST, port=RDB_PORT, db=RDB_DB)
    except RqlDriverError:
        debug("Could not connect to the database", True)
        abort(503, "No database connection could be established.")

@app.teardown_request
def teardown_request(exception):
    try:
        g.rdb_conn.close()
    except AttributeError:
        debug("Could not close a connection", True)
        pass


# Get the first movie
@app.route("/init")
def get_init_movie():
    id_movie = request.args.get('id_movie', '')
    # See if we have cache this data
    movie = r.table("movie").get(id_movie).do( lambda movie:
        r.branch(
            (movie == None) | (~movie.has_fields("similar_movies_id")), # If we didn't find the movie or didn't find the similar movies
            movie,                                                      # We just return the movie/None
            movie.merge({                                               # Else we add a field similar_movies with the relevant data
                "similar_movies": movie["similar_movies_id"].map(lambda similar_movie_id:
                    r.table("movie").get(similar_movie_id)
                )
            })
        )).run( g.rdb_conn )

    if movie is None:
        # Movie not found
        # Fetch similar movies from Rotten Tomatoes and save it
        movie = fetch_movie(id_movie)
        if "id" in movie: # If id is defined, we have a valid object
            r.table("movie").insert( movie ).run( g.rdb_conn, noreply=True) # Dump it in the database
        else:
            answer = {"error": "Movie not found. API rate limit reached?"}
            return json.dumps(answer)

    if "similar_movies" not in movie:
        # Movie found or fetched but similar movies not available.
        http_answer = fetch_movie(movie["id"])

        if "movies" in http_answer: # We found some similar movies
            # Dump the similar movies data in the database
            r.table("movie").insert( http_answer["movies"] ).run( noreply=True)

            # Update the similar movie of the current movie
            similar_movies_id = map(get_id, http_answer["movies"])
            r.table("movie").get(id_movie).update({"similar_movies_id": similar_movies_id }).run( g.rdb_conn, noreply=True)

            # Update the returned object
            movie["similar_movies"] = http_answer["movies"]
            return json.dumps(movie)
        else:
            # We could get the movie but not similar movies
            answer = {
                "error": "No similar movies returned. API rate limit reached?",
                "movie": movie
            }
            return json.dumps(answer)
    else:
        # Movie and its similar ones found
        return json.dumps(movie)


# Get similar movies
@app.route("/get")
def get_movie():
    id_movie = request.args.get('id_movie', '')

    # Get the similar movies
    result = r.table("movie").get(id_movie).do(lambda movie:
        r.branch( (movie != None) & (movie.has_fields("similar_movies_id")),
            r.expr({"id":id_movie}).merge({"similar_movies": movie["similar_movies_id"].map(lambda similar_movie_id:
                r.table("movie").get(similar_movie_id)
            )}),
            None
        )).run( g.rdb_conn )

    if result is None:
        # Fetch similar movies from Rotten Tomatoes and save it
        debug("Get movie: Fetching data from Rotten tomatoes for %s." % (id_movie))

        url = "http://api.rottentomatoes.com/api/public/v1.0/movies/"+str(id_movie)+"/similar.json?apikey="+API_KEY
        http_answer = do_http_request(url, None)
        if "movies" in http_answer:
            # Rename the field movies
            http_answer["similar_movies"] = http_answer["movies"]
            http_answer.pop("movies", None)

            # Dunp data in the database
            r.table("movie").insert( http_answer["similar_movies"] ).run( g.rdb_conn, noreply=True)

            # Update the original movie with its similar ones
            similar_movies_id = map(get_id, http_answer["similar_movies"])
            r.table("movie").get(id_movie).update({"similar_movies_id": similar_movies_id }).run( g.rdb_conn, noreply=True)

            # Add the id of the original movie so we can keep track of it in the js callback
            http_answer['id'] = id_movie
            return json.dumps(http_answer)
        else:
            answer = {"error": "No similar movies returned. API rate limit reached?"}
            return json.dumps(answer)
    else:
        debug("Get movie: found cache for %s." % (id_movie))
        return json.dumps(result)


# Not tested
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
        r.table("movie").insert(content_json["movies"]).run( g.rdb_conn, noreply=True )
        return content_json["movies"]
    else:
        return "[]"


# Serving all the content if you don't have nginx/apache. 
# Note: This is not secure, use it only for local development.
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def catch_all(path):
#     return send_from_directory('../web/', path)



# Non flask methods

def fetch_movie(id_movie):
    url = "http://api.rottentomatoes.com/api/public/v1.0/movies/"+str(id_movie)+".json"
    return do_http_request(url, None)

def fetch_similar(id_movie):
    url = "http://api.rottentomatoes.com/api/public/v1.0/movies/"+str(movie["id"])+"/similar.json?apikey="+API_KEY
    return do_http_request(url, None)

# Just used to map ids
def get_id(movie):
    return movie["id"]

def do_http_request(url, values):
    # Send HTTP POST request
    if values == None:
        values = {}
    values["apikey"] = API_KEY

    try:
        response = requests.get(url, params=values)
    except:
        #TODO return an appropriate error
        return {}
    else:
        return response.json()


def load_conf():
    global API_KEY
    global RDB_HOST
    global RDB_PORT
    global RDB_DB
    global DEBUG

    config = configparser.ConfigParser()
    config.read('app.conf')

    # We should probably wrap these little things in some try/except
    API_KEY = config.get('DEFAULT', "API_KEY")
    RDB_HOST = config.get('DEFAULT', "RDB_HOST")
    RDB_DB = config.get('DEFAULT', "RDB_DB")
    RDB_PORT = int(config.get('DEFAULT', "RDB_PORT"))
    DEBUG = int(config.get('DEFAULT', "DEBUG"))
    if DEBUG is 1:
        app.debug = True



def init_database():
    try:
        connection = r.connect(host=RDB_HOST, port=RDB_PORT, db=RDB_DB)
    except RqlDriverError:
        debug("Could not connect to the database %s:%d, exiting..." % (RDB_HOST, RDB_PORT), True)
        exit(1)

    try:
        r.db_create("tomatoesfridge").run( connection )
    except r.errors.RqlRuntimeError as e:
        # We could parse the error... later...
        debug("Database `tomatoesfridge` not created. Reason:")
        debug(str(e))
    else:
        debug("Database `tomatoesfridge` created")

    try:
        r.table_create("movie").run( connection )
    except r.errors.RqlRuntimeError as e:
        # We could parse the error... later...
        debug("Table `movie` in `tomatoesfridge` not created. Reason")
        debug(str(e))
    else:
        debug("Table `movie` in `tomatoesfridge` created")

    try:
        connection.close()
    except AttributeError:
        debug("Could not close a connection", True)
        pass


def debug(x, force_print=False):
    if DEBUG is 1 | force_print:
        print x

if __name__ == "__main__":
    load_conf()
    init_database()

    cherrypy.tree.graft(app, '/')
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 4000,
        })
    cherrypy.engine.start()
    cherrypy.engine.block()
