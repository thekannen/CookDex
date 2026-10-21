"""Held-out pages for the junk filter, written without looking at its rules."""
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


def parsed(quantity: float | None, unit: str | None, food: str, note: str = "") -> dict[str, Any]:
    display = " ".join(
        part for part in [
            ("" if quantity is None else (str(int(quantity)) if float(quantity).is_integer() else str(quantity))),
            unit or "",
            food,
            note,
        ] if part
    )
    return {
        "quantity": quantity,
        "unit": {"name": unit} if unit else None,
        "food": {"name": food},
        "note": note,
        "display": display,
    }


JUNK = [
    # --- about / contact / policy / site pages -------------------------------------------------
    page(
        "Hi, I'm Dana",
        "hi-im-dana",
        description="Home cook, mom of two, and recovering pastry school dropout.",
        steps=[
            "Welcome to the kitchen! I started this little corner of the internet in 2014 when my oldest was a "
            "baby and I needed something that was just mine. Back then it was mostly blurry photos of casseroles.",
            "These days you'll find weeknight dinners that actually get eaten, a lot of sourdough experiments, and "
            "the occasional dessert that took me six tries. Everything here is tested in my regular old kitchen "
            "with a temperamental oven.",
            "When I'm not cooking you can find me at the farmers market or hiding from laundry. Thanks for being here.",
        ],
    ),
    page(
        "The Team",
        "the-team",
        ingredients=["Editor-in-Chief", "Recipe Developer", "Photographer", "Follow on Instagram"],
        steps=[
            "Marcus Bell, Editor-in-Chief. Marcus oversees everything you read on the site and still insists on "
            "testing every chili recipe personally.",
            "Priya Raman, Recipe Developer. Priya spent eight years on the line in Chicago before joining us and "
            "now develops most of our baking content.",
            "Leo Fontaine, Photographer. If a photo on this site makes you hungry, Leo probably took it.",
        ],
    ),
    page(
        "Reader Favorites",
        "reader-favorites",
        description="The recipes you keep coming back to, all in one place.",
        steps=[
            "Not sure where to start? These are the posts that get the most love in the comments and the most "
            "saves on Pinterest. Click any photo below to jump to the full recipe.",
            "Updated every January based on the previous year's traffic.",
        ],
    ),
    page(
        "Cookbook Preorder",
        "cookbook-preorder",
        ingredients=["Amazon", "Barnes & Noble", "Bookshop.org", "Indigo"],
        steps=[
            "It's finally happening! Weeknights at Home, my first cookbook, comes out this spring with 100 recipes, "
            "80 of them brand new and never seen on the blog.",
            "Preorders matter so much for first-time authors. If you order before release day, forward your "
            "receipt to the address below and I'll send you a bonus digital chapter of holiday baking.",
        ],
    ),
    page(
        "Accessibility",
        "accessibility",
        steps=[
            "We are committed to making our website accessible to everyone, including people with disabilities. "
            "We aim to conform to WCAG 2.1 level AA guidelines.",
            "If you have trouble accessing any content on this site, please reach out using the form on our "
            "Contact page and we will do our best to provide the information in an alternative format.",
        ],
    ),
    page(
        "Get in Touch",
        "get-in-touch",
        ingredients=["Brand partnerships", "Media inquiries", "Recipe questions"],
        steps=[
            "I read every message, though it can take me a week or two to reply. For recipe questions, the "
            "comments section on the post is usually the fastest way to get an answer, since other readers chime in too.",
            "For sponsored content and brand collaborations, please include your timeline and budget.",
        ],
    ),
    page(
        "Disclosure Policy",
        "disclosure-policy",
        steps=[
            "This site contains affiliate links. If you click a link and make a purchase, I may receive a small "
            "commission at no additional cost to you. As an Amazon Associate I earn from qualifying purchases.",
            "All opinions are my own, and I only recommend products I use in my own kitchen.",
        ],
    ),
    page(
        "Privacy",
        "privacy",
        steps=[
            "This privacy notice describes how we collect, use and share information when you visit the site. "
            "We use cookies and similar technologies provided by our ad management partner.",
            "You may opt out of personalized advertising at any time. California residents have additional rights "
            "under the CCPA, described below.",
            "Last updated March 2, 2025.",
        ],
    ),
    page(
        "Join the Supper Club",
        "join-the-supper-club",
        ingredients=["Email address", "First name"],
        steps=[
            "Get a free weekly meal plan, a shopping list, and first dibs on new recipes every Sunday morning. "
            "No spam, ever. Unsubscribe whenever you like.",
        ],
    ),
    page(
        "Kitchen Tools I Love",
        "kitchen-tools-i-love",
        ingredients=["Lodge cast iron skillet", "Microplane zester", "OXO kitchen scale", "Shop now"],
        steps=[
            "People ask me all the time what's in my kitchen, so here is the gear I actually reach for every day. "
            "Some of these links are affiliate links.",
            "My 10-inch cast iron skillet was a wedding gift and has probably cooked a thousand dinners. If you "
            "only buy one thing on this list, make it a digital scale.",
        ],
    ),
    page(
        "Work With Me",
        "work-with-me",
        steps=[
            "With over 400,000 monthly readers and an engaged community across Instagram and TikTok, I partner "
            "with food and lifestyle brands that fit naturally into a home kitchen. Media kit available on request.",
        ],
    ),
    # --- trip / travel write-ups ---------------------------------------------------------------
    page(
        "Three Nights in Oaxaca",
        "three-nights-in-oaxaca",
        ingredients=["Mercado 20 de Noviembre", "Hierve el Agua", "Where we stayed"],
        steps=[
            "We landed late on a Thursday and went straight to the market for tlayudas, which was the right call. "
            "The smoke alley inside Mercado 20 de Noviembre is exactly as chaotic and wonderful as everyone says.",
            "Day two was a mezcal tasting outside the city. Our guide walked us through the whole process from "
            "roasting the agave hearts in pits to the stone tahona.",
            "If you only have a few days, don't overschedule. Some of our best meals happened because we wandered.",
        ],
    ),
    page(
        "Kyoto Diaries",
        "kyoto-diaries",
        description="Temples, tofu, and far too many matcha soft serves.",
        steps=[
            "Kyoto in late November is crowded but the maple leaves make it worth it. We rented bikes and spent "
            "most mornings riding along the river before the tour buses arrived.",
            "Nishiki Market deserves a full afternoon. Go hungry and bring cash.",
        ],
    ),
    page(
        "Notes from Normandy",
        "notes-from-normandy",
        steps=[
            "Butter, cream, apples, and cider. That's Normandy in four words. We based ourselves in a farmhouse "
            "near Honfleur for a week and ate cheese at every single meal.",
            "The Camembert farm tour was a highlight, and so was the tiny crêperie in Étretat where the owner "
            "insisted we try the salted caramel with a glass of pommeau.",
        ],
    ),
    page(
        "48 Hours in Lisbon",
        "48-hours-in-lisbon",
        ingredients=["Pastéis de Belém", "Time Out Market", "Alfama"],
        steps=[
            "Lisbon is hilly, so wear good shoes. Start your first morning at the famous custard tart bakery in "
            "Belém and get there before 9 if you want to skip the line.",
            "For dinner, skip the touristy spots along Rua Augusta and head up to a tasca in Alfama.",
        ],
    ),
    page(
        "A Week on the Amalfi Coast",
        "a-week-on-the-amalfi-coast",
        steps=[
            "We split our time between Positano and Ravello, and honestly the bus ride between them was the most "
            "terrifying part of the whole week.",
            "Lemons everywhere. Lemon granita, lemon pasta, limoncello after every dinner. I came home with three "
            "bottles in my suitcase.",
            "Ferries are the easiest way to get around if the sea is calm. Book the Capri day trip early in summer.",
        ],
    ),
    page(
        "Where We Ate in Mexico City",
        "where-we-ate-in-mexico-city",
        ingredients=["Roma Norte", "Condesa", "Coyoacán", "Map at bottom of post"],
        steps=[
            "This is the list I send to every friend who asks. Tacos al pastor at the little stand on the corner "
            "of our block, churros at El Moro, and the best tamales from a cart outside the metro.",
            "We tried to do one sit-down meal a day and street food for everything else. It worked.",
        ],
    ),
    page(
        "Our Hokkaido Winter",
        "our-hokkaido-winter",
        steps=[
            "Sapporo during the snow festival is magical. We ate miso ramen nearly every night and crab at the "
            "Nijo market every morning.",
        ],
    ),
    page(
        "Postcards from Sicily",
        "postcards-from-sicily",
        description="Palermo street food, Etna wine, and a very long ferry.",
        steps=[
            "Palermo's markets are loud and smell amazing. We had arancine for breakfast at least twice.",
            "Driving to Etna we stopped at a winery that let us taste straight from the barrels. The landscape up "
            "there feels like another planet, black lava fields with vines growing right out of them.",
            "Next time I want to spend more time on the east coast around Siracusa.",
        ],
    ),
    page(
        "Weekend in the Hudson Valley",
        "weekend-in-the-hudson-valley",
        ingredients=["Apple picking", "Farm stands", "Book a cabin"],
        steps=[
            "We drove up Friday afternoon and got to the cabin just before sunset. Saturday was apple picking, a "
            "cider donut or three, and a long dinner at a farm-to-table spot in Hudson.",
        ],
    ),
    page(
        "Istanbul, Finally",
        "istanbul-finally",
        steps=[
            "I've wanted to go for ten years and it did not disappoint. We took the ferry across the Bosphorus "
            "just for the views and ate simit with tea on the deck.",
            "The Spice Bazaar is touristy but fun, and Kadıköy on the Asian side is where we had our favorite "
            "meals. Our hotel was walking distance from Hagia Sophia.",
        ],
    ),
    page(
        "Road Tripping Through Vermont",
        "road-tripping-through-vermont",
        steps=[
            "Our loop: Burlington, Stowe, Woodstock, and back. Creemees at every stop. Cabot cheese factory. "
            "Maple sugar houses that were sadly closed for the season.",
            "Fall foliage peaks around the first week of October up north.",
        ],
    ),
    page(
        "Seoul Eats",
        "seoul-eats",
        ingredients=["Gwangjang Market", "Myeongdong", "Mangwon"],
        steps=[
            "Bindaetteok at Gwangjang, hotteok from a street cart, and an absurd amount of Korean fried chicken. "
            "We stayed in Mapo and took the subway everywhere, it's incredibly easy.",
            "Tip: download Naver Maps before you go. Google Maps walking directions don't work well there.",
        ],
    ),
    # --- personal story / update posts ---------------------------------------------------------
    page(
        "We're Moving!",
        "were-moving",
        steps=[
            "Big news: after twelve years in this apartment, we bought a house! It has a real kitchen with a "
            "gas range and a pantry the size of my old bathroom.",
            "Posting will be slow for the next few weeks while we pack and unpack. Thanks for your patience.",
        ],
    ),
    page(
        "A Little Break",
        "a-little-break",
        steps=[
            "I've been quiet here lately and I wanted to explain. My dad got sick this spring and I've been "
            "spending most of my time with him. Cooking has been simple comfort food and not much photographing.",
            "I'll be back soon. Thank you for all the kind emails.",
        ],
    ),
    page(
        "Ten Years of Blogging",
        "ten-years-of-blogging",
        description="What a decade of posting recipes has taught me.",
        steps=[
            "Ten years ago today I hit publish on a lopsided banana bread with a photo taken under a yellow "
            "kitchen light. I had no idea what I was doing.",
            "Since then this site has grown more than I ever imagined, and I've learned a few things: test "
            "everything twice, write like you talk, and never trust an oven dial.",
            "Thank you to every reader who has made one of my recipes and come back to tell me about it.",
        ],
    ),
    page(
        "Our Kitchen Renovation",
        "our-kitchen-renovation",
        ingredients=["Before", "During", "After", "Sources"],
        steps=[
            "Six months, two contractors, and one flooded basement later, the kitchen is done. We went with "
            "white oak cabinets, a soapstone counter, and finally an island big enough to roll out pie dough.",
            "Paint color is Farrow & Ball Pigeon. Hardware links below.",
        ],
    ),
    page(
        "What I'm Grateful For This Year",
        "what-im-grateful-for-this-year",
        steps=[
            "Every November I try to write one of these. This year: a healthy family, a garden that actually "
            "produced tomatoes, and all of you who keep cooking along with me.",
        ],
    ),
    page(
        "Welcome Baby Theo",
        "welcome-baby-theo",
        steps=[
            "He's here! Theo arrived on Tuesday at 7 lbs 4 oz and we are completely in love. I'm taking a few "
            "weeks of maternity leave, but I've scheduled some favorite posts from the archive to keep you company.",
        ],
    ),
    page(
        "Monthly Update: March",
        "monthly-update-march",
        ingredients=["What I'm reading", "What I'm cooking", "Links I loved"],
        steps=[
            "March flew by. I finally finished the sourdough series, spoke at a food writing conference in "
            "Portland, and adopted a very anxious rescue cat named Biscuit.",
            "Coming up in April: lots of spring vegetables and a giveaway with one of my favorite knife makers.",
        ],
    ),
    page(
        "Why I Stopped Counting Calories",
        "why-i-stopped-counting-calories",
        steps=[
            "For most of my twenties I tracked every bite. This post is a little more personal than usual, but a "
            "lot of you have asked why I don't include nutrition info anymore.",
            "Food is about more than numbers for me now. It's family, it's memory, it's the way my grandmother's "
            "kitchen smelled on Sunday afternoons.",
        ],
    ),
]


RECIPES = [
    # --- place / travel words in titles --------------------------------------------------------
    page(
        "Tuscan White Bean Soup",
        "tuscan-white-bean-soup",
        ingredients=[
            "2 tablespoons olive oil", "1 onion, diced", "3 cloves garlic, minced", "2 cans cannellini beans",
            "4 cups vegetable broth", "1 bunch lacinato kale, chopped", "1 parmesan rind", "salt and pepper",
        ],
        steps=[
            "Heat the olive oil in a large pot and cook the onion until soft, about 6 minutes. Add the garlic.",
            "Add the beans, broth, and parmesan rind. Simmer 20 minutes.",
            "Stir in the kale and cook until wilted. Remove the rind, season, and serve with crusty bread.",
        ],
        recipeYield="6 servings",
        totalTime="PT40M",
    ),
    page(
        "Paris-Brest",
        "paris-brest",
        ingredients=[
            "1/2 cup water", "1/2 cup milk", "1/2 cup butter", "1 cup flour", "4 eggs", "1/4 cup sliced almonds",
            "1 cup praline paste", "2 cups pastry cream", "powdered sugar",
        ],
        steps=[
            "Bring water, milk, and butter to a boil. Add flour all at once and stir until a ball forms.",
            "Off the heat, beat in the eggs one at a time. Pipe into a 9-inch ring on a lined sheet, sprinkle with almonds.",
            "Bake at 400F for 35 minutes until deep golden. Cool completely and split horizontally.",
            "Fold praline paste into pastry cream, pipe onto the base, replace the top, and dust with powdered sugar.",
        ],
        recipeYield="8 servings",
    ),
    page(
        "Road Trip Granola Bars",
        "road-trip-granola-bars",
        description="Chewy, packable bars for long drives.",
        ingredients=[
            "2 cups rolled oats", "1/2 cup honey", "1/2 cup peanut butter", "1/2 cup chocolate chips",
            "1/4 cup dried cranberries",
        ],
        steps=[
            "Warm the honey and peanut butter together until smooth.",
            "Stir in the oats, then the chocolate chips and cranberries. Press into a lined 8x8 pan and chill 2 hours before cutting.",
        ],
    ),
    page(
        "Hawaiian Vacation Punch",
        "hawaiian-vacation-punch",
        ingredients=["4 cups pineapple juice", "2 cups orange juice", "1 liter ginger ale", "1 cup coconut rum", "maraschino cherries"],
        steps=["Combine juices and rum in a punch bowl, top with ginger ale and ice, and garnish with cherries."],
    ),
    page(
        "Montreal Bagels",
        "montreal-bagels",
        ingredients=[
            "4 cups bread flour", "1 packet instant yeast", "1 egg", "1/3 cup honey", "2 tbsp oil", "1 cup warm water",
            "1/3 cup honey for boiling", "sesame seeds",
        ],
        steps=[
            "Mix flour, yeast, egg, honey, oil and water into a stiff dough. Knead 10 minutes and rest 20.",
            "Divide into 12 pieces, roll into ropes, and join into rings.",
            "Boil in honey water for 1 minute per side, coat in sesame seeds, and bake at 450F until browned, about 15 minutes.",
        ],
        recipeYield="12 bagels",
    ),
    page(
        "Singapore Sling",
        "singapore-sling",
        ingredients=[
            "1 1/2 oz gin", "1/2 oz cherry liqueur", "1/4 oz Cointreau", "1/4 oz Benedictine", "2 oz pineapple juice",
            "1/2 oz lime juice", "dash grenadine", "dash Angostura bitters",
        ],
        steps=["Shake everything with ice and strain into a highball glass over fresh ice. Garnish with a cherry and pineapple."],
    ),
    page(
        "New England Clam Chowder",
        "new-england-clam-chowder",
        ingredients=[
            parsed(4, "slice", "bacon", "chopped"), parsed(1, None, "onion", "diced"),
            parsed(2, "cup", "potatoes", "diced"), parsed(3, "can", "chopped clams"), parsed(2, "cup", "milk"),
            parsed(1, "cup", "heavy cream"), parsed(2, "tablespoon", "flour"),
        ],
        steps=[
            "Cook the bacon in a heavy pot until crisp. Add onion and cook until soft, then stir in the flour.",
            "Add the clam juice and potatoes and simmer until tender. Stir in clams, milk, and cream and heat through without boiling.",
        ],
        recipeYield="6 servings",
        totalTime="PT45M",
    ),
    page(
        "Philly Cheesesteak",
        "philly-cheesesteak",
        ingredients=["1 lb ribeye, shaved thin", "1 onion, sliced", "provolone or Cheez Whiz", "4 hoagie rolls", "oil"],
        steps=[
            "Caramelize the onion on a griddle, push aside, and cook the steak quickly, chopping it with a spatula.",
            "Top with cheese, let it melt, and scoop into the split rolls.",
        ],
    ),
    page(
        "Swedish Meatballs",
        "swedish-meatballs",
        ingredients=[
            "1 lb ground beef", "1/2 lb ground pork", "1/2 cup breadcrumbs", "1/4 cup milk", "1 egg",
            "1/4 tsp allspice", "3 tbsp butter", "3 tbsp flour", "2 cups beef broth", "1/2 cup sour cream",
        ],
        steps=[
            "Soak breadcrumbs in milk, then mix with the meats, egg, allspice, salt and pepper. Roll into 1-inch balls.",
            "Brown in butter and remove. Whisk flour into the pan, add broth, and simmer until thick.",
            "Stir in sour cream, return meatballs, and simmer 10 minutes. Serve with lingonberry jam.",
        ],
    ),
    page(
        "Moscow Mule",
        "moscow-mule",
        ingredients=["2 oz vodka", "1/2 oz lime juice", "4 oz ginger beer"],
        steps=["Pour into a copper mug over ice and stir."],
    ),
    page(
        "Black Forest Cake",
        "black-forest-cake",
        ingredients=[
            "1 chocolate sponge, split into 3 layers", "1 jar sour cherries in syrup", "3 tbsp kirsch",
            "2 cups heavy cream", "1/4 cup sugar", "chocolate shavings",
        ],
        steps=[
            "Drain the cherries, reserving syrup. Mix 1/2 cup syrup with the kirsch and brush over each cake layer.",
            "Whip cream with sugar. Layer cake, cream and cherries, then frost the outside and press on chocolate shavings.",
        ],
        recipeYield="12 slices",
    ),
    page(
        "Camping Trip Foil Packet Potatoes",
        "camping-trip-foil-packet-potatoes",
        ingredients=["potatoes", "onion", "butter", "salt", "pepper"],
        steps=[
            "Slice the potatoes and onion thin, pile onto heavy foil with a few pats of butter, season, and seal tightly. "
            "Cook on campfire coals or a grill for 25 to 30 minutes, flipping once.",
        ],
    ),
    # --- very short recipes ---------------------------------------------------------------------
    page(
        "Whipped Cream",
        "whipped-cream",
        ingredients=["1 cup heavy cream", "2 tbsp powdered sugar"],
        steps=["Whip until soft peaks form."],
    ),
    page(
        "Cinnamon Toast",
        "cinnamon-toast",
        ingredients=["bread", "butter", "cinnamon sugar"],
        steps=["Toast the bread, butter it while hot, and sprinkle generously with cinnamon sugar."],
    ),
    page(
        "Affogato",
        "affogato",
        ingredients=["1 scoop vanilla gelato", "1 shot hot espresso"],
        steps=["Pour the espresso over the gelato and eat immediately."],
    ),
    page(
        "Quick Pickled Red Onions",
        "quick-pickled-red-onions",
        ingredients=["1 red onion, thinly sliced", "1/2 cup apple cider vinegar", "1 tbsp sugar", "1 tsp salt"],
        steps=["Pack the onion into a jar, stir the vinegar, sugar and salt with 1/2 cup hot water until dissolved, pour over, and wait 30 minutes."],
    ),
    # --- chatty first-person instructions -------------------------------------------------------
    page(
        "My Grandma's Sunday Pot Roast",
        "my-grandmas-sunday-pot-roast",
        ingredients=[
            "3 lb chuck roast", "salt", "pepper", "2 tbsp oil", "1 onion", "4 carrots", "1 lb baby potatoes",
            "2 cups beef broth", "2 sprigs rosemary",
        ],
        steps=[
            "Okay so first things first, I always pat the roast really dry and salt it the night before if I remember. "
            "I usually don't remember, and it's still great, so don't stress.",
            "Get your Dutch oven screaming hot with the oil and sear that roast on every side. I mean really brown it, "
            "this is where all the flavor comes from. Grandma never rushed this part.",
            "Toss in the onion, carrots and potatoes around it, pour in the broth, add the rosemary, put the lid on, "
            "and let it go in a 300F oven for about 3 1/2 hours. My house smells incredible by hour two.",
            "It's done when you can shred it with a fork. I like to spoon the juices over everything before serving.",
        ],
        recipeYield="6 servings",
        totalTime="PT4H",
    ),
    page(
        "The Brownies I Make Every Single Week",
        "the-brownies-i-make-every-single-week",
        ingredients=[
            "1/2 cup butter", "1 cup sugar", "2 eggs", "1 tsp vanilla", "1/3 cup cocoa powder", "1/2 cup flour",
            "1/4 tsp salt",
        ],
        steps=[
            "I melt the butter right in a saucepan and then honestly just do everything in that one pot because I hate dishes.",
            "Whisk in the sugar, then the eggs and vanilla. Then I dump in the cocoa, flour and salt and stir until I can't see any dry bits.",
            "Spread it into a greased 8-inch pan and bake at 350F for 22 to 25 minutes. I pull mine when the middle still looks a tiny bit underdone because I like them fudgy. My husband disagrees, but he's wrong.",
        ],
    ),
    page(
        "Lazy Weeknight Fried Rice",
        "lazy-weeknight-fried-rice",
        ingredients=["leftover rice", "eggs", "frozen peas and carrots", "soy sauce", "sesame oil", "green onions"],
        steps=[
            "This is what I make when I open the fridge and there's nothing. You want cold rice, day-old is best. "
            "I crank the heat on my biggest skillet, scramble a couple of eggs, and set them aside.",
            "Then the veggies go in, then the rice, and I press it down and leave it alone for a minute so it gets crispy. "
            "Splash of soy, drizzle of sesame oil, eggs back in, green onions on top. Done in ten minutes, I promise.",
        ],
    ),
    # --- ingredients without amounts ------------------------------------------------------------
    page(
        "Roasted Broccoli",
        "roasted-broccoli",
        ingredients=["broccoli", "olive oil", "salt", "garlic powder", "lemon"],
        steps=[
            "Cut broccoli into florets, toss with olive oil, salt and garlic powder, and roast at 425F for 20 minutes "
            "until the edges char. Squeeze lemon over before serving.",
        ],
    ),
    page(
        "Caprese Salad",
        "caprese-salad",
        ingredients=["tomatoes", "fresh mozzarella", "basil", "olive oil", "flaky salt", "balsamic glaze"],
        steps=["Slice tomatoes and mozzarella, alternate on a platter with basil leaves, drizzle with oil and balsamic, and season."],
    ),
    page(
        "Garlic Bread",
        "garlic-bread",
        ingredients=["baguette", "butter", "garlic", "parsley", "parmesan"],
        steps=[
            "Mash softened butter with minced garlic and chopped parsley.",
            "Split the baguette, spread with the butter, top with parmesan, and broil until golden.",
        ],
    ),
    # --- long trip-story descriptions followed by a real recipe ---------------------------------
    page(
        "Lemon Spaghetti from Our Trip to Sorrento",
        "lemon-spaghetti-from-our-trip-to-sorrento",
        description=(
            "Last summer we spent ten days on the coast south of Naples, and every restaurant seemed to have its own "
            "version of this dish. We stayed in a little guesthouse above a lemon grove, and the owner, Lucia, taught "
            "me her version on our last night while her husband poured limoncello. I've made it at home at least "
            "thirty times since. It's the closest I can get to that terrace without a plane ticket."
        ),
        ingredients=[
            "1 lb spaghetti", "4 tbsp butter", "zest and juice of 2 lemons", "1 cup grated parmesan",
            "1/2 cup reserved pasta water", "black pepper", "basil",
        ],
        steps=[
            "Cook the spaghetti in well-salted water until al dente. Reserve a cup of the water before draining.",
            "Melt the butter in the pot, add the lemon zest and juice, then the pasta and parmesan. Toss vigorously, "
            "adding pasta water until glossy. Finish with pepper and torn basil.",
        ],
        recipeYield="4 servings",
        totalTime="PT20M",
    ),
    page(
        "Pastel de Nata",
        "pastel-de-nata",
        description=(
            "I first tried these on a rainy morning in Lisbon, standing in a line that wrapped around the block. "
            "We went back three more times before our flight home. After a lot of failed batches, this is the version "
            "that finally tastes like Belém to me: blistered tops, shattering pastry, and a just-set custard."
        ),
        ingredients=[
            "1 sheet puff pastry", "1 cup whole milk", "2 tbsp flour", "2/3 cup sugar", "1/3 cup water",
            "1 cinnamon stick", "strip of lemon peel", "6 egg yolks",
        ],
        steps=[
            "Roll the pastry into a tight log, slice into 12 rounds, and press each into a muffin cup.",
            "Simmer sugar, water, cinnamon and lemon peel to a syrup. Whisk the flour into the milk and heat until thick.",
            "Strain the syrup into the milk, cool slightly, and whisk in the yolks.",
            "Fill the shells and bake at 550F for 9 to 12 minutes until blackened in spots.",
        ],
        recipeYield="12 tarts",
    ),
    page(
        "Chicken Khao Soi",
        "chicken-khao-soi",
        description=(
            "Our honeymoon ended with a week in Chiang Mai, and the noodle shop around the corner from our hotel ruined "
            "every other soup for me. I came home and went straight to the Asian grocery. This one takes some hunting "
            "for ingredients but it's worth it."
        ),
        ingredients=[
            "3 tbsp red curry paste", "1 tbsp curry powder", "2 cans coconut milk", "2 cups chicken stock",
            "1 1/2 lb chicken thighs", "2 tbsp fish sauce", "1 tbsp palm sugar", "egg noodles",
            "shallots, pickled mustard greens, lime, for serving",
        ],
        steps=[
            "Fry the curry paste and curry powder in a splash of coconut cream until fragrant.",
            "Add the rest of the coconut milk, stock, and chicken. Simmer 25 minutes, then shred the chicken and season with fish sauce and sugar.",
            "Serve over boiled noodles, topped with crispy fried noodles, shallots, mustard greens and a lime wedge.",
        ],
    ),
    page(
        "Irish Brown Bread",
        "irish-brown-bread",
        description=(
            "We drove the Ring of Kerry over a long weekend and every B&B served a slightly different loaf of this with "
            "breakfast. No yeast, no kneading."
        ),
        ingredients=[
            parsed(2, "cup", "whole wheat flour"), parsed(1, "cup", "all-purpose flour"),
            parsed(1, "teaspoon", "baking soda"), parsed(1, "teaspoon", "salt"),
            parsed(2, "cup", "buttermilk"), parsed(1, "tablespoon", "molasses"),
        ],
        steps=[
            "Whisk the dry ingredients, then stir in buttermilk and molasses to make a wet, shaggy dough.",
            "Shape into a round on a floured sheet, cut a deep cross on top, and bake at 425F for 40 minutes.",
        ],
        recipeYield="1 loaf",
    ),
    # --- misc tricky ----------------------------------------------------------------------------
    page(
        "Thanksgiving Leftover Sandwich",
        "thanksgiving-leftover-sandwich",
        ingredients=["2 slices sourdough", "leftover turkey", "stuffing", "cranberry sauce", "gravy"],
        steps=["Pile everything on the bread, griddle it in butter until crisp, and dip in warm gravy."],
    ),
    page(
        "Mom's Holiday Fudge",
        "moms-holiday-fudge",
        ingredients=["1 can sweetened condensed milk", "3 cups chocolate chips", "1 tsp vanilla"],
        steps=["Melt the condensed milk and chips together over low heat, stir in vanilla, pour into a lined pan, and chill until firm."],
    ),
    page(
        "Shrimp and Grits",
        "shrimp-and-grits",
        ingredients=[
            parsed(1, "cup", "stone-ground grits"), parsed(4, "cup", "water"), parsed(1, "cup", "sharp cheddar", "shredded"),
            parsed(1, "pound", "shrimp", "peeled"), parsed(4, "slice", "bacon"), parsed(2, "clove", "garlic"),
            parsed(None, None, "green onions"),
        ],
        steps=[
            "Simmer the grits in salted water, stirring often, for 30 minutes. Stir in cheddar.",
            "Cook the bacon, then saute the shrimp and garlic in the drippings. Spoon over grits with bacon and green onions.",
        ],
        totalTime="PT45M",
    ),
    page(
        "Margherita Pizza",
        "margherita-pizza",
        ingredients=["1 ball pizza dough", "1/2 cup crushed San Marzano tomatoes", "4 oz fresh mozzarella", "basil", "olive oil"],
        steps=["Stretch the dough, top with tomatoes and torn mozzarella, and bake on a preheated stone at 550F for 7 minutes. Finish with basil and oil."],
    ),
]


CORPUS = [(p, "junk") for p in JUNK] + [(p, "recipe") for p in RECIPES]
