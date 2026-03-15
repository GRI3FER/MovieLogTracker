My Website tracks movies and shows I either want to watch, am watching or have watched. 
I chose this because there's a ton of shows I've been trying to watch, but I keep forgetting
to watch them and end up scrolling reels instead. So I made this website to help me keep track of that.

Table: movies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                platform     TEXT,
                genre        TEXT,
                rating       INTEGER CHECK(rating BETWEEN 1 AND 5),
                date_watched TEXT,
                notes        TEXT,
                status       TEXT NOT NULL DEFAULT 'watched',
                rank         INTEGER,
                poster_path  TEXT,
                media_type   TEXT
            )
id is a unique identifier for each movie/show
title is movie title
platform is on what platform I watched the movie
genre is what genre is the movie
rating is what I rated the movie (between 1 and 5)
date_watched is when I watched the movie
notes are any notes I had
status is whetehr it is watched, want to watch or watching
rank is how I rank movies in want to watch
poster_path is the path to the poster image using TDMB (the api I used)
media_type is just between movies, cartoons, anime and tv shows

To run the app just download the files on the Github and do python app.py and it should open on http://localhost:5000/

To Create an entry click add entry on the top right, the status will be auto selected depending on which tab out of Watched, Watching or Want to Watch it's in
To Read click whichever tab and all the entries are displayed
To Update click the edit button on whichever movie box you want to change
To Delete click the delete button on whichever movie box you want to delete
