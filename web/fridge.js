var DEFAULT_MOVIE = '770671912';
var HEADER_HEIGHT = 41;
var movies = [];
var nodes = movies;
var labelAnchors = [];
var labelAnchorLinks = [];
var links = [];

// faster search
var movies_hash = {}
var links_hash = {}
var timeout_error = null

function show_error(error) {
    $('.feedback').html(error);
    $('.feedback_container').fadeIn();
    if (timeout_error != null) clearTimeout(timeout_error);
    timeout_error = setTimeout(hide_error, 3000);
}
function handle_http_error(data) {
    if (data["status"] != null) { 
        show_error("Ajax request failed with status "+data["status"]+".");
    }
    else {
        show_error("Ajax request failed.");
    }
    $('.loader').hide();
}
function hide_error() {
    $('.feedback_container').fadeOut();
    timeout_error = null;
}

// Get the first movie
function init_movie(movie_id) {
    $('.loader').show(); // In a perfect world, we would have a counter
    $.ajax({
        url: 'api/init?id_movie='+movie_id,
        dataType: 'json',
        type: 'get',
        success: save_first_movie,
        error: handle_http_error
    });
}

// Callback for first movie
function save_first_movie(data) {
    if (data['error'])
        return show_error(data['error']);

    movies.push(data);
    movies_hash[data['id']] = 0;
    labelAnchors.push({ node: data });
    labelAnchors.push({ node: data });

    labelAnchorLinks.push({
        source : labelAnchors[labelAnchors.length-2],
        target : labelAnchors[labelAnchors.length-1],
        weight : 1
    });
    if (data['similar_movies'] != null) {
        update_data(data);
    }
    else {
        get_movie(data['id']);
    }
}

// Get similar movies
function get_movie(movie_id) {
    $('.loader').show(); // In a perfect world, we would have a counter
    $.ajax({
        url: 'api/get?id_movie='+movie_id,
        dataType: 'json',
        type: 'get',
        success: update_data,
        error: handle_http_error
    });
}

// Callback for similar movies
function update_data(data) {
    $('.loader').hide();

    if (data['error'])
        return show_error(data['error']);

    for(var i in data['similar_movies']) {
        movie = data['similar_movies'][i];
        if (movies_hash[movie['id']] == null){
            //TODO: Give movie a position
            /*
            movie.x = nodes[movies_hash[data['id']]].x+Math.random()*30;
            movie.y = nodes[movies_hash[data['id']]].y+Math.random()*30;
            */
            movies.push(movie);

            labelAnchors.push({ node: movie, /*x: movie.x, y: movie.y*/ });
            labelAnchors.push({ node: movie, /*x: movie.x, y: movie.y*/ });

            labelAnchorLinks.push({
                source : labelAnchors[labelAnchors.length-2],
                target : labelAnchors[labelAnchors.length-1],
                weight : 10
            });

            movies_hash[movie['id']] = movies.length-1;
        }
        if (data['id'] < movie['id']) {
            hash_link = data['id'] + '#' + movie['id'];
        }
        else {
            hash_link = movie['id'] + '#' + data['id'];
        }
        if (links_hash[hash_link] == null) {
            new_link = {
                target: nodes[movies_hash[data['id']]],
                source: nodes[movies_hash[movie['id']]],
                weight: 1//Math.random()
            }
            links.push(new_link);
            links_hash[hash_link] = true;
        }
    }
    draw_movies();
}

// Draw new movies
function draw_movies() {
    var w = $(window).width();
    var h = $(window).height()-HEADER_HEIGHT;

    var click_position = {
            x: Math.floor(w/2),
            y: Math.floor(h/2)
    }

    var labelDistance = 0;

    // Resize svg
    var vis = d3.select("svg").attr("width", w).attr("height", h).select('g.wrap');

    // Create force between nodes
    var force = d3.layout.force().friction(0.8).size([w, h]).nodes(nodes).links(links).gravity(0.1).linkDistance(10*nodes.length).charge(-3000).linkStrength(function(x) {
        return x.weight;
    });
    force.start();


    // Create second force for labels
    var force2 = d3.layout.force().friction(0.3/(Math.max(1,labelAnchors.length/10))).nodes(labelAnchors).links(labelAnchorLinks).gravity(0.05).linkDistance(1).linkStrength(1).charge(-500).size([w, h]);
    force2.start();

    // Draw lines
    var link = vis.selectAll("line.link").data(links).enter().append("svg:line").attr("class", "link").style("stroke", "#CCC");

    // Draw nodes
    var node = vis.selectAll("g.node").data(force.nodes()).enter().append("svg:g").attr("class", "node");
    node.append("svg:circle").attr("r", 5).style("fill", "#555").style("stroke", "#FFF").style("stroke-width", 3)
        .on("click", function(d, i){
            click_position = {
                x: (event.x!=event.x)? Math.floor(w/2): event.x,
                y: (event.y!=event.y)? Math.floor(h/2): event.y
            }
            get_movie(d.id);
        });



    // "Draw" anchors links
    var anchorLink = vis.selectAll("line.anchorLink").data(labelAnchorLinks);//.enter().append("svg:line").attr("class", "anchorLink").style("stroke", "#999");
        //.enter().append("svg:line").attr("class", "anchorLink").style("stroke", "#999");

    var anchorNode = vis.selectAll("g.anchorNode").data(force2.nodes()).enter().append("svg:g").attr("class", "anchorNode");
    anchorNode.append("svg:circle").attr("r", 0).style("fill", "#FFF");
    anchorNode.append("svg:text").text(function(d, i) {
        return i % 2 == 0 ? "" : d.node.title
    }).style("fill", "#555").style("font-family", "Arial").style("font-size", 12)
        //.style("opacity", 0)
        .attr("data-id", function(d, i) {
        return d.node.id
    }).on("mousedown", function(d, i) {
        show_info(d, event);
    });

    var updateLink = function() {
        this.attr("x1", function(d) {       
            if (d.source.x != d.source.x) { d.source.x = click_position.x }
            return d.source.x;
        }).attr("y1", function(d) {
            if (d.source.y != d.source.y) { d.source.y = click_position.y };
            return d.source.y;
        }).attr("x2", function(d) {
            if (d.target.x != d.target.x) { d.target.x = click_position.x };
            return d.target.x;
        }).attr("y2", function(d) {
            if (d.target.y != d.target.y) { d.target.y = click_position.y };
            return d.target.y;
        });
    }

    var updateNode = function() {
        this.attr("transform", function(d) {
            //if (d.x!=d.x) d.x=0;
            //if (d.y!=d.y) d.y=0;
            return "translate(" + d.x + "," + d.y + ")";
        });
    }
    var resetNode = function() {
        this.attr("transform", function(d) {
            //if (d.x!=d.x) d.x=0;
            //if (d.y!=d.y) d.y=0;
            return "translate(0, 0)";
        });
    }

    force.on("tick", function() {
        // Move clicked point closer to the middle
        //TODO


        vis.selectAll("g.node").call(updateNode);
        var start_force2 = true;
        vis.selectAll("g.anchorNode").each(function(d, i) {
            if(i % 2 == 0) {
                d.x = d.node.x;
                d.y = d.node.y;
            }
            else {
                var desired_distance = 20;
                var b = this.childNodes[1].getBBox();

                var diffX = d.x - d.node.x;
                var diffY = d.y - d.node.y;

                // Distance between text and anchor
                var dist = Math.sqrt(diffX * diffX + diffY * diffY);
                var old_dist = dist;
                if (dist == 0) {
                    diffX = Math.random()*max_dist;
                    diffY = Math.random()*max_dist;
                    dist = Math.sqrt(diffX * diffX + diffY * diffY);

                    d.x = d.node.x+diffX/dist*max_dist;
                    d.y = d.node.y+diffY/dist*max_dist;

                    diffX = d.x - d.node.x;
                    diffY = d.y - d.node.y;

                    // Distance between text and anchor
                    dist = Math.sqrt(diffX * diffX + diffY * diffY);
                    start_force2 = false;
                   
                }
                else if (dist == dist && (dist != desired_distance)) {
                    d.x = d.node.x+diffX/dist*desired_distance;
                    d.y = d.node.y+diffY/dist*desired_distance;

                    diffX = d.x - d.node.x;
                    diffY = d.y - d.node.y;

                    // Distance between text and anchor
                    dist = Math.sqrt(diffX * diffX + diffY * diffY);
                    start_force2 = false;
                }
                
                var shiftX = b.width * (diffX - dist) / (dist * 2);
                shiftX = Math.max(-b.width, Math.min(0, shiftX));
                var shiftY = 5;

                /*
                var new_dist = Math.sqrt(shiftX * shiftX + shiftY * shiftY);
                shiftX = shiftX/new_dist*10;
                shiftY = shiftY/new_dist*10;
                */
                if ((shiftX == shiftX) && (shiftY == shiftY)) {
                    this.childNodes[1].setAttribute("transform", "translate(" + shiftX + "," + shiftY + ")");
                }
                else {
                    force2.start();
                }
            }
        });
        if (start_force2 == true) {
            force2.start();
        }

        vis.selectAll("g.anchorNode").call(updateNode);

        //link.call(updateLink);
        vis.selectAll("line.link").call(updateLink);

        vis.selectAll("line.anchorLink").call(updateLink);
    });
}

// Show extra stuff
function show_info(data, event) {
    event.stopPropagation();
    event.preventDefault();
    if ($('.movie_container').css('display') == 'block') {
        $('.movie_container').fadeOut('fast', function() {
            update_info(data);
        });
    }
    else {
        update_info(data);
    }
}
function update_info(data) {
    $('.movie_title').html(data.node.title);
    $('.audience_score').width( data.node.ratings.audience_score+'%');
    $('.critics_score').width(data.node.ratings.critics_score+'%');
    $('.more > a').attr("href", data.node.links.alternate);
    $('.critic').html(data.node.critics_consensus);
    $('.movie_container').fadeIn('fast');
}
function hide_info() {
    $('.movie_container').fadeOut('fast');
}
function hide_help(cb) {
    $('.help_container').fadeOut('fast', cb);
}
function hide_about(cb) {
    $('.about_container').fadeOut('fast', cb);
}
function show_help(cb) {
    $('.help_container').fadeIn('fast', cb);
}
function show_about(cb) {
    $('.about_container').fadeIn('fast', cb);
}

var translate_values; // keep it global
$(document).ready( function() {
    svg_container = $('.container');
    svg_jquery= $('.main_svg');

    // Bind mouse events for translation
    var mousedown = false;
    translate_values = {x:0, y:0};
    var previous_position;
    var svg = d3.select("svg");
    var wrap = svg.select("g.wrap");

    svg.on('mousedown', function(e) {
            mousedown = true;
            previous_position = {
                x: event.x,
                y: event.y
            }
            svg_jquery.addClass('disable-select');
            hide_info();
            hide_help();
            hide_about();
        })
        .on('mousemove', function(e) {
            if (mousedown) {
                translate_values.x += event.x-previous_position.x;
                translate_values.y += event.y-previous_position.y;
                
                wrap.attr("transform", function(d) {
                    return "translate(" + translate_values.x + "," + translate_values.y + ")";
                });

                previous_position.x = event.x;
                previous_position.y = event.y;

            }
        })
        .on('mouseup', function(e) {
            mousedown = false;
            svg_jquery.removeClass('disable-select');
        });

    $('.help_link').click( function(e) {
        e.preventDefault();
        if ($('.help_container').css('display') == 'block') {
            hide_help()
        }
        else {
            if ($('.about_container').css('display') == 'block') {
                hide_about(show_help);
            }
            else {
                show_help();
            }
        }
    });
    $('.about_link').click( function(e) {
        e.preventDefault();
        if ($('.about_container').css('display') == 'block') {
            hide_about()
        }
        else {
            if ($('.help_container').css('display') == 'block') {
                hide_help(show_about);
            }
            else {
                show_about()
            }
        }
    });

    $('.close').click( function(e) {
        e.preventDefault();
        hide_info();
    });

    init_movie(DEFAULT_MOVIE);

});

