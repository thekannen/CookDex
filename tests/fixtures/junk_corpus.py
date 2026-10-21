"""Real-looking pages for testing the junk filter.

Each entry is a recipe as Mealie returns it, with what it really is:
``"junk"`` (an about, contact, policy, trip or story page) or ``"recipe"``.
Pages are written the way food blogs write them, and the way Mealie's scraper
brings them in: site pages often come with a few stray lines as ingredients
and a paragraph or two as steps.
"""
from __future__ import annotations

from typing import Any


def page(name: str, slug: str, *, steps: list[str], ingredients: list[Any] = (), description: str = "",
         **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "slug": slug,
        "description": description,
        "recipeIngredient": [i if isinstance(i, dict) else {"note": i, "display": i} for i in ingredients],
        "recipeInstructions": [{"text": text} for text in steps],
        **extra,
    }


# ── About, contact and policy pages ──────────────────────────────────

ABOUT_PAGES = [
    page("About", "about", steps=[
        "Hi! I'm Sarah, the cook and photographer behind Sarah's Kitchen. I started this blog in 2015 as a way to keep "
        "track of the meals I made for my family, and it grew into a community of home cooks from all over the world.",
        "When I'm not in the kitchen you'll find me hiking with my husband and our two dogs. Thanks for being here!",
    ]),
    page("Meet Jenn", "meet-jenn", ingredients=["Follow me on Instagram", "Pinterest"], steps=[
        "My name is Jenn and I'm a former pastry chef turned stay-at-home mom. Welcome to my little corner of the "
        "internet, where I share the easy, family-friendly recipes we actually eat.",
        "I live in Ohio with my husband, three kids and a very spoiled cat. Subscribe to my newsletter so you never miss a post.",
    ]),
    page("Contact", "contact-2", steps=[
        "Have a question about a recipe? I'd love to hear from you! Fill out the form below and I'll get back to you "
        "within a few days. For brand partnerships, please email me directly.",
        "Please note that I can't answer every message, but I read them all.",
    ]),
    page("Work With Me", "work-with-me", steps=[
        "I partner with brands I genuinely love and use in my own kitchen. My audience is home cooks who want reliable "
        "weeknight dinners. I offer sponsored posts, recipe development and social media campaigns.",
        "Download my media kit or get in touch to talk about working together.",
    ]),
    page("Privacy Policy", "privacy", steps=[
        "This privacy policy explains how we collect, use and protect your personal information when you visit this "
        "site. We use cookies and third-party services such as analytics and advertising networks.",
        "The information we collect may include your email address when you subscribe to our newsletter. We never sell "
        "your data to third parties. All rights reserved.",
    ]),
    page("Disclosure Policy", "disclosure-policy", steps=[
        "Some posts on this blog contain affiliate links. If you click one and make a purchase, I may earn a commission "
        "at no extra cost to you. As an Amazon Associate I earn from qualifying purchases.",
    ]),
    page("Our Story", "our-story", ingredients=["Two home cooks", "One tiny kitchen"], steps=[
        "We are Mike and Lisa, two home cooks who met in culinary school and never stopped arguing about the right way "
        "to make lasagna. We started this blog to settle it once and for all.",
        "Ten years and two kids later, we're still arguing, and we've shared hundreds of the recipes we love along the way.",
    ]),
    page("Welcome to Grandma's Table", "welcome-to-grandmas-table", steps=[
        "Welcome to my blog! This blog is a collection of the recipes my grandmother taught me, written down so they "
        "don't get lost. Subscribe to the newsletter and follow me on Facebook for new posts every week.",
    ]),
    page("Terms and Conditions", "terms-and-conditions", steps=[
        "By using this website you agree to these terms of service. All content, including photographs and text, is "
        "copyright and may not be reproduced without permission. All rights reserved.",
    ]),
    page("Start Here", "start-here", steps=[
        "New here? Welcome! I'm so glad you found my site. If you're not sure where to begin, I've rounded up my most "
        "popular posts below. Don't forget to subscribe to my newsletter and follow me on Instagram.",
    ]),
    page("FAQ", "faq", steps=[
        "Can I freeze the cookies? Yes. Let them cool completely, then freeze them in a bag for up to three months.",
        "Do you have a cookbook? Not yet, but I'm working on it! Subscribe to my newsletter to be the first to know.",
        "Can I use your photos? Please ask first. Contact me through the form on the contact page.",
    ]),
    page("Shop", "shop-my-kitchen", steps=[
        "These are the kitchen tools I use every day. As an Amazon Associate I earn a commission on qualifying "
        "purchases, which helps keep this blog running. Thank you for your support!",
    ]),
]

# ── Trip and travel posts ────────────────────────────────────────────

TRIP_POSTS = [
    page("Our Week in Tuscany", "our-week-in-tuscany",
         ingredients=["Day 1: Florence", "Day 2: Siena", "Day 3: Montepulciano", "Day 4: the farmhouse"],
         steps=[
             "Last month we flew into Florence and spent a week exploring the Tuscan countryside. We stayed in a "
             "restored farmhouse outside Siena and spent our days wandering hill towns and eating far too much pasta.",
             "The highlight was a long lunch at a tiny family restaurant in Montepulciano, where the owner's mother "
             "made pici by hand. We visited three wineries and I still dream about the pecorino we bought at the market.",
         ]),
    page("A Long Weekend in Lisbon", "long-weekend-lisbon", steps=[
        "We took a quick trip to Lisbon over the long weekend and I'm already planning to go back. Our hotel was in "
        "the Alfama district, all steep streets and tiled houses.",
        "We ate pastel de nata every single morning and took the famous tram up to the castle. If you go, book the "
        "food tour on your first day so you know where to eat for the rest of the trip.",
    ]),
    page("What We Ate in Tokyo", "what-we-ate-in-tokyo",
         ingredients=["Ramen at Ichiran", "Sushi at Tsukiji Outer Market", "Tonkatsu", "Convenience store egg sandwiches"],
         steps=[
             "Tokyo has been at the top of our travel list for years, and it was worth the wait. We landed at Haneda "
             "airport late at night and went straight for a bowl of ramen.",
             "Over ten days we visited every neighborhood we could, from Shinjuku to Asakusa, and I'm sharing every "
             "place we ate so you can plan your own itinerary.",
         ]),
    page("Road Trip Through the South", "road-trip-south", steps=[
        "This summer we packed up the car and drove two thousand miles through Tennessee, Georgia and the Carolinas, "
        "stopping at every barbecue joint we could find along the way.",
        "Our favorite was a little roadside smokehouse outside Memphis. We stayed in small towns, visited old diners "
        "and came home with a trunk full of hot sauce.",
    ]),
    page("Honeymoon in Santorini", "honeymoon-santorini", steps=[
        "We just got back from our honeymoon in Santorini and I have so many photos to share. Our resort had the most "
        "incredible view of the caldera, and we watched the sunset from Oia every night.",
        "The food was simple and perfect: grilled octopus, fava and tomato fritters by the sea.",
    ]),
    page("Paris in the Spring", "paris-in-the-spring", steps=[
        "There's nothing like Paris in April. We visited the Louvre, climbed to Sacré-Cœur and spent a whole afternoon "
        "in the cafés of the Marais. Our little apartment was right above a boulangerie.",
        "I've put together a guide to the bakeries we loved most, from croissants to macarons, for anyone planning a trip.",
    ]),
    page("Back From Vietnam!", "back-from-vietnam", description="Two weeks, five cities, a lot of pho.", steps=[
        "We just landed after two weeks traveling from Hanoi to Ho Chi Minh City, and I'm still a little jet-lagged.",
        "We took the overnight train to Hue, explored the old town of Hoi An by bike and ate street food on tiny plastic "
        "stools every night. I'll be sharing the dishes we're trying to recreate at home soon.",
    ]),
    page("Exploring the Markets of Marrakech", "markets-of-marrakech", steps=[
        "The souks of Marrakech are a feast for the senses. We spent our first morning lost in the spice markets, "
        "where vendors piled cumin and saffron into towering cones.",
        "Our riad's host took us on a walking tour of the medina, and we visited a cooking school on our last day. "
        "It was the trip of a lifetime.",
    ]),
    page("Our Family Trip to Maine", "family-trip-maine",
         ingredients=["Lobster rolls at Red's Eats", "Blueberry pie", "Whoopie pies", "Fried clams"],
         steps=[
             "Every August we rent the same little cottage on the coast of Maine, and this year the kids finally "
             "learned to love lobster. We drove up the coast to Bar Harbor and hiked in Acadia.",
             "We visited the farmers market in Camden and stayed until the last ferry. Here's everything we ate.",
         ]),
    page("Summer Vacation Recap", "summer-vacation-recap", steps=[
        "What a summer! Our vacation this year took us to the lake, where we stayed in my parents' cabin for two weeks. "
        "We swam every morning, grilled most nights and read a pile of books.",
        "I didn't cook much, which was the whole point. Now it's back to school and back to the kitchen.",
    ]),
    page("Mexico City Travel Guide", "mexico-city-travel-guide", steps=[
        "Mexico City is one of the best food cities in the world. In this travel guide I share where we stayed, the "
        "museums worth your time, and the taco stands we visited again and again.",
    ]),
    page("Five Days in Seoul", "five-days-seoul", steps=[
        "Our flight landed early, so we dropped our luggage at the hotel and went straight to Gwangjang Market. "
        "We visited palaces in the morning and ate fried chicken late into the night.",
    ]),
]

# ── Stories that aren't recipes ──────────────────────────────────────

STORY_POSTS = [
    page("Life Lately", "life-lately", steps=[
        "It's been a crazy few months around here. My youngest started kindergarten, we finally finished painting the "
        "living room, and I've been working on something big that I can't wait to tell you about.",
        "I know I haven't posted much lately, and I'm sorry. Thank you all for sticking with me. I'll be back with new "
        "posts soon, I promise. In the meantime, I'd love to hear what you've been up to.",
    ]),
    page("Thank You for 10 Years!", "ten-years", steps=[
        "Ten years ago today I hit publish on my very first post. I had no idea that this little hobby would become my "
        "job, or that I'd meet so many of you along the way.",
        "Thank you for reading, for commenting, for sharing my posts with your friends. I couldn't have done any of it "
        "without you, and I'm so excited for what comes next.",
    ]),
    page("Why I Stopped Meal Prepping", "why-i-stopped-meal-prepping", steps=[
        "For years I spent every Sunday afternoon filling containers for the week ahead. It worked for a while, but "
        "honestly I got tired of eating the same thing five days in a row, and my family did too.",
        "These days I keep it loose. I plan two or three dinners, keep the pantry stocked, and let the rest of the week "
        "happen. I'm happier, and we waste less food.",
    ]),
    page("Our Kitchen Renovation", "kitchen-renovation", steps=[
        "After six long months, our kitchen renovation is finally done! We knocked down a wall, moved the sink to the "
        "island and I finally have the big pantry I always wanted.",
        "I'm sharing before and after photos and where we found everything, from the tiles to the light fixtures.",
    ]),
]

# ── Real recipes that must never be deleted on their own ─────────────

TRICKY_RECIPES = [
    page("Tuscan Chicken", "tuscan-chicken", description="Inspired by our trip to Tuscany last spring.",
         ingredients=["4 chicken breasts", "2 tablespoons olive oil", "3 cloves garlic, minced", "1 cup heavy cream",
                      "1/2 cup sun-dried tomatoes", "2 cups fresh spinach"],
         steps=["Season the chicken with salt and pepper.", "Heat the oil in a large skillet and sear the chicken until golden, about 5 minutes per side.",
                "Add the garlic, cream and tomatoes and simmer for 3 minutes.", "Stir in the spinach and serve."],
         recipeYield="4 servings", totalTime="30 minutes"),
    page("Paris-Brest", "paris-brest",
         ingredients=["1/2 cup water", "1/2 cup milk", "1/2 cup butter", "1 cup flour", "4 eggs", "1 cup praline paste"],
         steps=["Preheat the oven to 400°F.", "Bring the water, milk and butter to a boil, then stir in the flour.",
                "Beat in the eggs one at a time and pipe a ring onto a lined sheet.", "Bake 35 minutes, cool, split and fill with praline cream."]),
    page("Road Trip Trail Mix", "road-trip-trail-mix",
         ingredients=["1 cup peanuts", "1 cup raisins", "1/2 cup chocolate candies", "1 cup pretzels"],
         steps=["Mix everything in a large bowl.", "Divide into bags for the road trip."]),
    page("Road Trip Trail Mix (no amounts)", "road-trip-trail-mix-2",
         ingredients=["peanuts", "raisins", "chocolate candies", "pretzels"],
         steps=["Toss everything together and pack into bags for the car. Perfect for a long trip!"]),
    page("Mexican Street Corn (Elotes)", "mexican-street-corn",
         ingredients=["4 ears corn", "1/4 cup mayonnaise", "1/2 cup cotija", "1 lime", "1 tsp chili powder"],
         steps=["Grill the corn until charred.", "Brush with mayonnaise, roll in cotija and sprinkle with chili powder.", "Serve with lime."]),
    page("Singapore Noodles", "singapore-noodles",
         ingredients=["8 oz rice vermicelli", "1 tbsp curry powder", "8 oz shrimp", "2 eggs", "1 red pepper, sliced"],
         steps=["Soak the noodles in hot water for 10 minutes and drain.", "Stir-fry the shrimp, push aside and scramble the eggs.",
                "Add the pepper, noodles and curry powder and toss until coated."]),
    page("Philly Cheesesteak", "philly-cheesesteak",
         ingredients=["1 lb ribeye, thinly sliced", "1 onion", "4 slices provolone", "4 hoagie rolls"],
         steps=["Cook the onion in a hot pan until soft.", "Add the beef and cook 2 minutes.", "Top with cheese, then pile into rolls."]),
    page("Grandma's Sunday Gravy", "grandmas-sunday-gravy",
         ingredients=["pork ribs", "Italian sausage", "crushed tomatoes", "garlic", "fresh basil"],
         steps=[
             "My grandmother always started this early on Sunday morning, before we left for church. We would brown "
             "the meat in her big pot while she crushed the garlic with the side of her knife.",
             "Then she added the tomatoes and let it simmer all day, stirring now and then, until we sat down to eat "
             "at three. I still make it the same way for my own kids.",
         ]),
    page("Simple Syrup", "simple-syrup", ingredients=["1 cup sugar", "1 cup water"],
         steps=["Heat until the sugar dissolves. Cool."]),
    page("Cinnamon Toast", "cinnamon-toast", ingredients=["bread", "butter", "cinnamon sugar"],
         steps=["Toast the bread, butter it and sprinkle with cinnamon sugar."]),
    page("Sun Tea", "sun-tea", ingredients=["4 tea bags", "1 gallon water"],
         steps=["Put the tea bags in a jar of water and leave it in the sun for 3 to 4 hours."]),
    page("Travel Mug Oatmeal", "travel-mug-oatmeal",
         ingredients=["1/2 cup rolled oats", "1 cup boiling water", "1 tbsp maple syrup"],
         steps=["Pour the oats and water into a travel mug, close and wait 5 minutes.", "Stir in the syrup."]),
    page("Camping Trip Foil Packets", "camping-trip-foil-packets",
         ingredients=["1 lb sausage, sliced", "4 potatoes, diced", "1 onion", "2 tbsp butter"],
         steps=["We make these on every camping trip with the kids.", "Divide everything between four sheets of foil and fold closed.",
                "Cook over hot coals for 25 minutes."]),
    page("Vacation Sangria", "vacation-sangria",
         ingredients=["1 bottle red wine", "1 orange, sliced", "1/4 cup brandy", "2 cups soda"],
         steps=["Combine the wine, orange and brandy in a pitcher and chill overnight.", "Top with soda before serving."]),
    page("Lettuce Alone (Honeymoon Salad)", "honeymoon-salad", ingredients=["1 head romaine", "2 tbsp vinaigrette"],
         steps=["Toss and serve."]),
    page("About Time Chili", "about-time-chili",
         ingredients=["2 lb ground beef", "2 cans kidney beans", "1 can tomatoes", "2 tbsp chili powder"],
         steps=["Brown the beef in a large pot.", "Add everything else and simmer for an hour."]),
    page("Contact Grill Panini", "contact-grill-panini",
         ingredients=["2 slices sourdough", "2 slices mozzarella", "4 basil leaves", "1 tomato, sliced"],
         steps=["Layer the cheese, basil and tomato between the bread.", "Press in a hot contact grill for 4 minutes."]),
    page("Nonna's Meatballs", "nonnas-meatballs",
         ingredients=["1 lb ground beef", "1/2 cup breadcrumbs", "1 egg", "1/4 cup parmesan"],
         steps=["I learned these from my nonna when I was little, and we still make them every Christmas.",
                "Mix everything with your hands, roll into balls and fry until browned. Then we drop them into the sauce."]),
    page("Lemon Ricotta Pasta", "lemon-ricotta-pasta",
         description="Last summer we traveled to Italy and visited a tiny village on the Amalfi coast, where we stayed with "
                     "a family who made this every night. I've made it at home ever since our trip.",
         ingredients=["12 oz spaghetti", "1 cup ricotta", "1 lemon, zested", "1/2 cup parmesan"],
         steps=["Cook the pasta in salted water.", "Whisk the ricotta, lemon and parmesan with a splash of pasta water.", "Toss and serve."]),
    page("Mealie-Parsed Beef Stew", "parsed-beef-stew",
         ingredients=[
             {"quantity": 2, "unit": {"name": "pound"}, "food": {"name": "beef chuck"}, "note": "", "display": "2 pound beef chuck"},
             {"quantity": 3, "unit": None, "food": {"name": "carrot"}, "note": "", "display": "3 carrot"},
             {"quantity": 1, "unit": {"name": "quart"}, "food": {"name": "beef stock"}, "note": "", "display": "1 quart beef stock"},
         ],
         steps=["Brown the beef in batches.", "Add the carrots and stock and simmer for 2 hours."], recipeServings=6),
    page("Day Trip Picnic Sandwiches", "day-trip-picnic-sandwiches",
         ingredients=["1 baguette", "4 oz ham", "4 oz brie", "2 tbsp butter"],
         steps=["Slice the baguette lengthwise, spread with butter and layer the ham and brie.", "Wrap tightly for the trip."]),
    page("London Fog Latte", "london-fog-latte", ingredients=["1 Earl Grey tea bag", "1 cup milk", "1 tsp vanilla", "1 tsp honey"],
         steps=["Steep the tea in 1/2 cup hot water for 5 minutes.", "Heat and froth the milk, then pour over the tea with the vanilla and honey."]),
    page("Our Trip to Greece + My Favorite Tzatziki", "greece-tzatziki",
         description="We spent two weeks traveling around the Greek islands, and I came home obsessed with tzatziki.",
         ingredients=["1 cup Greek yogurt", "1 cucumber, grated", "1 clove garlic", "1 tbsp olive oil", "1 tbsp dill"],
         steps=["Squeeze the grated cucumber dry.", "Stir everything together and chill for an hour before serving."]),
    page("Weeknight Fried Rice", "weeknight-fried-rice",
         ingredients=["3 cups cooked rice", "2 eggs", "1 cup frozen peas", "2 tbsp soy sauce"],
         steps=["Heat a wok, scramble the eggs and set aside.", "Fry the rice, add peas and soy sauce, then fold the eggs back in."]),
    page("Mom's Story Pancakes", "moms-pancakes",
         description="My mom made these every Saturday when I was growing up. I remember waking up to the smell and "
                     "running downstairs in my pajamas. Now my kids do the same thing, and I love it.",
         ingredients=["1 1/2 cups flour", "1 tbsp sugar", "2 tsp baking powder", "1 1/4 cups milk", "1 egg"],
         steps=["Whisk the dry ingredients.", "Add milk and egg and stir until just combined.", "Cook on a hot griddle until bubbles form, then flip."]),
    page("Charcuterie Board", "charcuterie-board", ingredients=["salami", "brie", "crackers", "grapes"], steps=[]),
]

JUNK = ABOUT_PAGES + TRIP_POSTS + STORY_POSTS
CORPUS = [(p, "junk") for p in JUNK] + [(p, "recipe") for p in TRICKY_RECIPES]
