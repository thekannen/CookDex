"""Second held-out set for the junk filter, written without looking at its rules."""
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
    parts = []
    if quantity is not None:
        parts.append(f"{quantity:g}")
    if unit:
        parts.append(unit)
    parts.append(food)
    display = " ".join(parts) + (f", {note}" if note else "")
    return {
        "quantity": quantity,
        "unit": {"name": unit} if unit else None,
        "food": {"name": food},
        "note": note,
        "display": display,
    }


JUNK = [
    page(
        "About Me",
        "about-me-2",
        description="Hi, I'm Jess! Home cook, mom of three, and lover of all things butter.",
        steps=[
            "I started this blog in 2014 as a way to keep track of the recipes my grandmother taught me. "
            "Since then it has grown into a community of over 200,000 home cooks who just want dinner on "
            "the table without the fuss. When I'm not in the kitchen you can find me at my kids' soccer "
            "games or hiking with our golden retriever, Biscuit.",
            "Want to work together? Check out my media kit or send me a note through the contact form.",
        ],
    ),
    page(
        "Get in Touch",
        "get-in-touch",
        ingredients=["Email", "Instagram", "Pinterest", "Business inquiries"],
        steps=[
            "I love hearing from readers! Please allow 3-5 business days for a response. If you have a "
            "question about a specific recipe, the fastest way to get an answer is to leave a comment on "
            "that post so other readers can benefit too.",
            "For brand partnerships and sponsored content, please email my manager directly.",
        ],
    ),
    page(
        "Privacy Policy",
        "privacy-policy-3",
        steps=[
            "This site uses cookies to improve your experience and to serve personalized ads through our "
            "ad network partner. By continuing to use this site you consent to our use of cookies.",
            "We collect information you provide directly, such as your name and email address when you "
            "subscribe to the newsletter. We never sell your personal information to third parties.",
            "You may request deletion of your data at any time by contacting us.",
        ],
    ),
    page(
        "Our Week in Lisbon",
        "our-week-in-lisbon",
        description="Pastéis de nata, tiled streets and way too many sardines.",
        ingredients=["Day 1: Alfama", "Day 2: Belém", "Day 3: Sintra", "Where we stayed"],
        steps=[
            "We landed in Lisbon early Tuesday morning after a red-eye and headed straight to our "
            "apartment in Alfama. The hills are no joke, so pack comfortable shoes! Our first stop was a "
            "tiny café where we had the best espresso of the trip.",
            "On day two we took the tram out to Belém and of course waited in line at the famous bakery. "
            "Worth every minute. In the afternoon we wandered the monastery and the waterfront.",
            "Sintra was the highlight for the kids. We booked tickets for Pena Palace in advance, which I "
            "highly recommend because the lines were enormous by 10 a.m.",
        ],
    ),
    page(
        "2026 Holiday Gift Guide for Home Cooks",
        "2026-holiday-gift-guide-for-home-cooks",
        ingredients=[
            "Enameled cast iron Dutch oven",
            "Microplane zester",
            "Digital instant-read thermometer",
            "Linen apron",
            "Flaky sea salt sampler",
        ],
        steps=[
            "Shopping for the cook in your life? I've rounded up the tools I actually use every single "
            "week, from splurge-worthy pieces to stocking stuffers under $20.",
            "This post contains affiliate links, which means I may earn a small commission at no extra "
            "cost to you if you make a purchase.",
        ],
    ),
    page(
        "What's in My Pantry",
        "whats-in-my-pantry",
        description="A peek inside the cupboards, plus the staples I always keep stocked.",
        ingredients=["Oils and vinegars", "Grains", "Canned goods", "Spices", "Baking"],
        steps=[
            "People ask me all the time what I keep on hand, so I finally pulled everything out of the "
            "pantry and took pictures. I'm a big believer that a well-stocked pantry is the secret to "
            "weeknight dinners.",
            "I buy most of my spices in bulk from a local shop and decant them into glass jars. Labels "
            "are from my label maker, which I'll link below.",
        ],
    ),
    page(
        "Spring Cooking Class: Fresh Pasta Workshop",
        "spring-cooking-class-fresh-pasta-workshop",
        ingredients=["Saturday, April 18", "10 a.m. to 1 p.m.", "Riverside Community Kitchen", "$85 per person"],
        steps=[
            "Join me for a hands-on fresh pasta workshop! We'll cover egg dough, shaping fettuccine and "
            "ravioli, and two simple sauces. All ingredients and equipment are provided, and you'll go "
            "home with a box of pasta you made yourself.",
            "Space is limited to 12 students. Registration closes one week before the class. Refunds are "
            "available up to 72 hours before the event.",
        ],
    ),
    page(
        "Giveaway: Stand Mixer (Closed)",
        "giveaway-stand-mixer-closed",
        steps=[
            "This giveaway is now closed. Congratulations to Megan R. from Ohio, who was selected at "
            "random! Thank you to everyone who entered and shared your favorite cookie memories.",
            "Stay tuned, because we have another giveaway coming next month with our friends at a "
            "cookware brand you're going to love.",
        ],
    ),
    page(
        "Holiday Hours",
        "holiday-hours",
        ingredients=["Thanksgiving: Closed", "Black Friday: 9-3", "Christmas Eve: 8-noon", "Christmas Day: Closed"],
        steps=[
            "Please note our bakery's adjusted hours for the holiday season. Pie pre-orders must be placed "
            "by November 20 and can be picked up the Tuesday or Wednesday before Thanksgiving.",
            "We'll be back to regular hours on January 2. Thank you for supporting a small local business!",
        ],
    ),
    page(
        "Reader Questions: Volume 7",
        "reader-questions-volume-7",
        steps=[
            "It's time for another round of reader questions! This month you asked about substituting "
            "gluten-free flour, whether you can freeze my enchiladas, and what camera I use.",
            "Q: Can I use almond milk in the pancake recipe? A: Yes, though they'll be a little less "
            "fluffy. Q: Where did you get your blue mixing bowls? A: They were a thrift store find years "
            "ago, sorry! Q: Do you ever take a break from cooking? A: Ha, every Friday is pizza night.",
            "Keep the questions coming in the comments and I'll answer more next month.",
        ],
    ),
    page(
        "Where We Ate in Mexico City",
        "where-we-ate-in-mexico-city",
        description="Tacos al pastor at 1 a.m., a tasting menu we're still talking about, and the best churros.",
        ingredients=["Roma Norte", "Condesa", "Coyoacán", "Centro Histórico"],
        steps=[
            "We spent five nights in Mexico City and ate our way through four neighborhoods. Below are the "
            "restaurants, taquerias and markets we loved, plus a couple we'd skip next time.",
            "The tasting menu was pricey but completely unforgettable. Book at least a month out. The mole "
            "course alone was worth the flight.",
            "Our last morning we went back to the same churro stand for the third time. No regrets.",
        ],
    ),
    page(
        "Life Update: We Moved!",
        "life-update-we-moved",
        steps=[
            "It's been quiet around here, and I wanted to explain why. After ten years in our little "
            "apartment we finally bought a house! The last two months have been a blur of boxes, "
            "paint chips and eating takeout on the floor.",
            "The new kitchen has a gas range and a huge island and I'm so excited to start shooting "
            "recipes in it. Thank you all for your patience. New posts start back up next week!",
        ],
    ),
    page(
        "Subscribe to the Newsletter",
        "subscribe-to-the-newsletter",
        ingredients=["First name", "Email address"],
        steps=[
            "Get new recipes delivered straight to your inbox every Sunday, plus a free printable weekly "
            "meal planner when you sign up. No spam, ever. Unsubscribe anytime.",
        ],
    ),
    page(
        "Shop",
        "shop",
        ingredients=["Signed cookbook", "Spice blend trio", "Recipe card set", "Tote bag"],
        steps=[
            "All orders ship within 3-5 business days. Free shipping on orders over $50 within the "
            "continental US. Gift wrapping is available at checkout.",
        ],
    ),
    page(
        "Disclosure",
        "disclosure",
        steps=[
            "This website is a participant in the Amazon Services LLC Associates Program, an affiliate "
            "advertising program designed to provide a means for sites to earn advertising fees by "
            "advertising and linking to Amazon.com. Nutritional information is provided as a courtesy "
            "and is an estimate only.",
        ],
    ),
    page(
        "Our Napa Valley Getaway",
        "our-napa-valley-getaway",
        steps=[
            "For our anniversary my husband surprised me with a long weekend in Napa. We stayed at a small "
            "inn in Yountville and biked between wineries. I'd never done a cave tour before and it was "
            "so much fun.",
            "Dinner the first night was at a farm-to-table spot where everything came from their garden. "
            "The second night we picnicked with cheese and bread from the market and watched the sunset.",
        ],
    ),
    page(
        "Meal Plan Monday: Week 32",
        "meal-plan-monday-week-32",
        ingredients=["Monday: Sheet Pan Gnocchi", "Tuesday: Taco Night", "Wednesday: Leftovers",
                     "Thursday: Lemon Chicken", "Friday: Pizza"],
        steps=[
            "Here's what we're eating this week! Click through to each recipe for the full ingredient list. "
            "Grab the printable grocery list at the bottom of the post.",
        ],
    ),
    page(
        "Thank You for 10 Years",
        "thank-you-for-10-years",
        steps=[
            "Ten years ago today I hit publish on my very first post, a blurry photo of banana bread taken "
            "on a flip phone. I could never have imagined where this little corner of the internet would "
            "take me: a cookbook, a TV appearance, and friendships with so many of you.",
            "From the bottom of my heart, thank you for cooking along with me.",
        ],
    ),
    page(
        "Farmers Market Haul + What I'm Making This Week",
        "farmers-market-haul-what-im-making",
        ingredients=["Heirloom tomatoes", "Sweet corn", "Peaches", "Zucchini", "Sunflowers"],
        steps=[
            "Saturday morning market trips are my favorite ritual. This week the peaches were finally "
            "perfect and I may have bought way too many. I also grabbed a bunch of sunflowers for the table.",
            "Over the next few days I'll be sharing what I make with everything, so keep an eye on "
            "Instagram stories for sneak peeks!",
        ],
    ),
    page(
        "Book Tour Dates",
        "book-tour-dates",
        ingredients=["Portland, OR - Oct 3", "Seattle, WA - Oct 5", "Denver, CO - Oct 9", "Chicago, IL - Oct 12"],
        steps=[
            "I'm hitting the road to celebrate the new cookbook! Each event includes a short talk, a Q&A, "
            "and a book signing. Tickets include a copy of the book. Links to each bookstore are below.",
        ],
    ),
    page(
        "Terms of Use",
        "terms-of-use",
        steps=[
            "All content, including photographs and text, is copyright protected. You are welcome to share "
            "a single photo with a link back to the original post, but please do not republish full recipes "
            "without written permission.",
            "We reserve the right to modify these terms at any time.",
        ],
    ),
    page(
        "Kitchen Tour",
        "kitchen-tour",
        description="The renovation is finally done!",
        steps=[
            "After six months of dust and a microwave on the dining table, the kitchen renovation is "
            "complete. We went with white oak cabinets, a soapstone counter and open shelving on one wall.",
            "Sources for the hardware, faucet and light fixtures are listed at the end of this post.",
        ],
    ),
    page(
        "Why I Stopped Meal Prepping",
        "why-i-stopped-meal-prepping",
        steps=[
            "For years Sunday was meal prep day. I'd spend four hours cooking and portioning containers, "
            "and by Wednesday nobody wanted to eat any of it. Last spring I gave it up and honestly our "
            "family eats better now.",
            "Instead I prep components: washed greens, a pot of grains, a jar of dressing. Then dinner is "
            "assembly. Let me know in the comments if you've tried this approach.",
        ],
    ),
    page(
        "Restaurant Review: Osteria on Fifth",
        "restaurant-review-osteria-on-fifth",
        ingredients=["Atmosphere: 4/5", "Service: 5/5", "Food: 4.5/5", "Price: $$$"],
        steps=[
            "We visited on a Thursday night and the place was packed. The cacio e pepe was silky and "
            "peppery, though the portion was small for the price. Our server was wonderful and steered us "
            "toward a great bottle of wine.",
            "Dessert was a slightly underwhelming panna cotta. Overall, I'd go back for the pasta alone.",
        ],
    ),
    page(
        "Summer Break Announcement",
        "summer-break-announcement",
        steps=[
            "Just a quick note to let you know I'm taking the month of August off to spend time with family. "
            "The recipe archive is still here for you, and I'll be back in September with lots of fall "
            "baking. See you soon!",
        ],
    ),
    page(
        "Weekend Links",
        "weekend-links-14",
        ingredients=["Read", "Watch", "Listen", "Buy"],
        steps=[
            "Happy Friday! A few things I loved this week: a fascinating article about the history of "
            "sourdough, a podcast episode about restaurant labor, and the cutest linen napkins on sale.",
            "Have a wonderful weekend, friends.",
        ],
    ),
    page(
        "Press and Features",
        "press-and-features",
        ingredients=["Good Morning America", "Food & Wine", "The Kitchn", "BuzzFeed"],
        steps=[
            "I'm honored to have been featured by these wonderful publications. For press inquiries please "
            "use the contact page.",
        ],
    ),
    page(
        "Road Trip Through Vermont",
        "road-trip-through-vermont",
        steps=[
            "Fall foliage season in Vermont is everything people say it is. We drove Route 100 from south "
            "to north over four days, stopping at cider mills, a cheese cave, and more maple stands than I "
            "can count.",
            "Tip: book lodging early, because peak weekend inns fill up months in advance.",
        ],
    ),
    page(
        "Recipe Index",
        "recipe-index",
        ingredients=["Breakfast", "Appetizers", "Soups", "Main Dishes", "Desserts", "Drinks"],
        steps=["Browse every recipe on the site by category, or use the search bar above."],
    ),
    page(
        "Supper Club Sign-Up",
        "supper-club-sign-up",
        steps=[
            "Our monthly supper club is back! Each month we pick a theme, everyone brings a dish, and we "
            "eat together at the community hall. October's theme is harvest. Sign up using the form "
            "below so we know how many tables to set up. Kids welcome.",
        ],
    ),
    page(
        "My Favorite Cookbooks of the Year",
        "my-favorite-cookbooks-of-the-year",
        ingredients=["The Weeknight Table", "Salt and Smoke", "Bake Simple", "A Year of Soup"],
        steps=[
            "Every December I share the cookbooks that earned a permanent spot on my shelf. This year's list "
            "leans heavily on vegetables and baking. All of these would make great gifts.",
        ],
    ),
]


RECIPES = [
    page(
        "Farmers Market Salad",
        "farmers-market-salad",
        description="Whatever looks good at the market, tossed with a quick lemon dressing.",
        ingredients=["tomatoes", "cucumber", "sweet corn", "basil", "olive oil", "lemon", "salt"],
        steps=["Cut everything into bite-size pieces, dress with olive oil, lemon and salt, and toss."],
    ),
    page(
        "Welcome Home Lasagna",
        "welcome-home-lasagna",
        description="The lasagna I make for friends when they get back from a long trip or bring home a new baby.",
        ingredients=[
            "1 lb Italian sausage",
            "1 jar (24 oz) marinara",
            "12 lasagna noodles",
            "15 oz ricotta",
            "1 egg",
            "3 cups shredded mozzarella",
            "1/2 cup grated Parmesan",
        ],
        steps=[
            "Heat the oven to 375°F. Brown the sausage in a skillet, then stir in the marinara.",
            "Mix the ricotta with the egg and half the Parmesan.",
            "Layer sauce, noodles, ricotta and mozzarella in a 9x13 dish, repeating three times and "
            "finishing with sauce and cheese.",
            "Cover with foil and bake 45 minutes, uncover and bake 15 more. Rest 15 minutes before cutting.",
        ],
        recipeYield="8 servings",
        totalTime="PT1H30M",
    ),
    page(
        "Our Story Cake",
        "our-story-cake",
        description="The vanilla cake from our wedding, which is how this whole blog started.",
        ingredients=[
            parsed(2.5, "cup", "all-purpose flour"),
            parsed(1.5, "cup", "sugar"),
            parsed(1, "cup", "butter", "softened"),
            parsed(4, None, "eggs"),
            parsed(1, "cup", "buttermilk"),
            parsed(2, "teaspoon", "baking powder"),
            parsed(1, "tablespoon", "vanilla extract"),
        ],
        steps=[
            "Cream the butter and sugar until fluffy, then beat in the eggs one at a time and the vanilla.",
            "Whisk the flour and baking powder, then add to the batter alternately with the buttermilk.",
            "Divide between two greased 9-inch pans and bake at 350°F for 30 to 35 minutes.",
        ],
    ),
    page(
        "Weekend Waffles",
        "weekend-waffles",
        ingredients=[
            "2 cups flour",
            "2 tbsp sugar",
            "1 tbsp baking powder",
            "1/2 tsp salt",
            "2 eggs",
            "1 3/4 cups milk",
            "1/2 cup melted butter",
        ],
        steps=[
            "Whisk the dry ingredients in one bowl and the wet in another, then stir together until just combined.",
            "Pour into a hot greased waffle iron and cook until golden and crisp.",
        ],
        recipeYield="6 waffles",
    ),
    page(
        "Holiday Punch",
        "holiday-punch",
        ingredients=["cranberry juice", "ginger ale", "orange juice", "frozen cranberries", "orange slices"],
        steps=["Combine everything in a punch bowl right before guests arrive."],
    ),
    page(
        "Grilled Chicken Thighs",
        "grilled-chicken-thighs-simple",
        ingredients=["chicken thighs", "salt", "pepper", "lemon", "garlic powder"],
        steps=[
            "Season the chicken all over.",
            "Grill over medium-high, about 6 minutes per side.",
            "Squeeze lemon over the top.",
        ],
    ),
    page(
        "Mom's Tuna Salad",
        "moms-tuna-salad",
        description="So first you're going to want to drain the tuna really, really well. That's the whole secret.",
        ingredients=["tuna", "mayo", "celery", "pickle relish", "salt and pepper"],
        steps=[
            "So first you're going to want to drain the tuna really well, like press it with a fork until "
            "nothing else comes out. Then I like to chop the celery super fine so you get the crunch without "
            "big chunks. Throw it all in a bowl with a big spoonful of mayo and some relish, and season to "
            "taste. My mom always served it on toasted rye but crackers are great too.",
        ],
    ),
    page(
        "Lazy Sunday Pot Roast",
        "lazy-sunday-pot-roast",
        ingredients=["chuck roast", "onion", "carrots", "potatoes", "beef broth", "rosemary"],
        steps=[
            "I like to sear the roast in my Dutch oven first because it makes such a difference in flavor, "
            "but if you're feeling lazy you can skip it. Pile the onions, carrots and potatoes around the "
            "meat, pour in enough broth to come about halfway up, tuck in a sprig of rosemary, and put the "
            "lid on. Then into a 300 degree oven for about three and a half hours, until it falls apart "
            "when you poke it.",
        ],
    ),
    page(
        "Classic Negroni",
        "classic-negroni",
        ingredients=["1 oz gin", "1 oz Campari", "1 oz sweet vermouth", "orange peel"],
        steps=["Stir with ice until cold, strain over a large cube, and garnish with the orange peel."],
    ),
    page(
        "Margarita on the Rocks",
        "margarita-on-the-rocks",
        ingredients=[
            parsed(2, "ounce", "blanco tequila"),
            parsed(1, "ounce", "lime juice", "fresh"),
            parsed(0.75, "ounce", "triple sec"),
            parsed(None, None, "kosher salt", "for the rim"),
        ],
        steps=["Salt the rim. Shake the tequila, lime and triple sec with ice and strain into the glass over fresh ice."],
    ),
    page(
        "Overnight Oats",
        "overnight-oats-basic",
        ingredients=["1/2 cup rolled oats", "1/2 cup milk", "1/4 cup yogurt", "1 tbsp chia seeds", "honey"],
        steps=["Stir everything together in a jar, cover, and refrigerate overnight. Top with fruit in the morning."],
        recipeYield="1 serving",
    ),
    page(
        "Green Smoothie",
        "green-smoothie-everyday",
        ingredients=["spinach", "frozen banana", "frozen mango", "almond milk"],
        steps=["Blend until smooth."],
    ),
    page(
        "Turkey and Swiss Sandwich",
        "turkey-and-swiss-sandwich",
        ingredients=["sourdough", "sliced turkey", "Swiss cheese", "dijon", "lettuce", "tomato"],
        steps=["Spread the bread with mustard and stack everything up. Cut on the diagonal, obviously."],
    ),
    page(
        "Cinnamon Toast",
        "cinnamon-toast",
        ingredients=["bread", "butter", "cinnamon sugar"],
        steps=["Toast the bread, butter it while hot, and shower it with cinnamon sugar."],
    ),
    page(
        "Watermelon Feta Salad",
        "watermelon-feta-salad",
        description="We had a version of this on a terrace in Crete during our honeymoon and I've been making it every summer since.",
        ingredients=["watermelon", "feta", "mint", "red onion", "olive oil", "flaky salt"],
        steps=["Cube the watermelon, crumble over the feta, scatter the mint and thinly sliced onion, then drizzle with oil and salt."],
    ),
    page(
        "Lemon Ricotta Pasta from Our Amalfi Coast Trip",
        "lemon-ricotta-pasta-amalfi-trip",
        description=(
            "Last June we spent ten days driving the Amalfi Coast, and I swear every lemon there is the size "
            "of a grapefruit. We rented a little apartment in Positano with a terrace overlooking the sea, "
            "and on our third night the owner's mother came up with a bag of lemons and showed us how she "
            "makes this pasta. We ate it four more times that week. The ferry to Capri, the hike on the Path "
            "of the Gods, the gelato in Ravello: all wonderful, but this is what I think about most."
        ),
        ingredients=[
            "1 lb spaghetti",
            "1 cup whole-milk ricotta",
            "2 lemons, zested and juiced",
            "1/2 cup grated Parmesan",
            "2 tbsp olive oil",
            "salt and black pepper",
        ],
        steps=[
            "Cook the spaghetti in well-salted water until al dente. Reserve 1 cup of pasta water.",
            "Whisk the ricotta, lemon zest, lemon juice, Parmesan and olive oil in a large bowl.",
            "Toss the hot pasta with the ricotta mixture, adding pasta water a splash at a time until creamy.",
            "Season with plenty of black pepper and serve right away.",
        ],
        recipeYield="4 servings",
        totalTime="PT25M",
    ),
    page(
        "Vacation Breakfast Burritos",
        "vacation-breakfast-burritos",
        description="I make a big batch before every beach vacation so we're not cooking the first morning.",
        ingredients=["eggs", "breakfast sausage", "frozen hash browns", "cheddar", "flour tortillas", "salsa"],
        steps=[
            "Brown the sausage, cook the hash browns until crisp, and scramble the eggs.",
            "Fill the tortillas with everything plus cheese and a spoonful of salsa, roll tightly, and wrap in foil.",
            "Freeze, then reheat in a 375°F oven for 25 minutes from frozen.",
        ],
    ),
    page(
        "Road Trip Trail Mix",
        "road-trip-trail-mix",
        ingredients=["peanuts", "raisins", "M&Ms", "pretzels", "cashews"],
        steps=["Mix it all in a big bowl and portion into bags."],
    ),
    page(
        "Travel Day Chicken Soup",
        "travel-day-chicken-soup",
        description="What I make the night we get home from any trip, when everyone is tired and the fridge is empty.",
        ingredients=["rotisserie chicken", "chicken broth", "carrots", "celery", "egg noodles", "dill"],
        steps=[
            "Simmer the broth with sliced carrots and celery until tender, about 10 minutes. Add the noodles "
            "and cook until done, then stir in shredded chicken and dill.",
        ],
    ),
    page(
        "Market Day Ratatouille",
        "market-day-ratatouille",
        ingredients=[
            parsed(1, None, "eggplant", "cubed"),
            parsed(2, None, "zucchini", "sliced"),
            parsed(1, None, "red bell pepper", "chopped"),
            parsed(1, None, "onion", "chopped"),
            parsed(3, "clove", "garlic", "minced"),
            parsed(1, "can", "crushed tomatoes"),
            parsed(3, "tablespoon", "olive oil"),
            parsed(None, None, "thyme"),
        ],
        steps=[
            "Sauté the onion and pepper in olive oil until soft, then add the garlic.",
            "Add the eggplant and zucchini and cook 10 minutes, then the tomatoes and thyme.",
            "Simmer, partially covered, for 30 minutes until everything is very tender.",
        ],
        recipeYield="6 servings",
    ),
    page(
        "About Time Brownies",
        "about-time-brownies",
        description="Named because it took me about forty tries to get them fudgy enough.",
        ingredients=[
            "10 tbsp butter",
            "1 1/4 cups sugar",
            "3/4 cup cocoa powder",
            "2 eggs",
            "1/2 cup flour",
            "1/2 tsp salt",
        ],
        steps=[
            "Melt the butter with the sugar and cocoa, then let it cool a few minutes.",
            "Beat in the eggs one at a time, then fold in the flour and salt.",
            "Bake in a lined 8-inch pan at 325°F for 22 to 25 minutes.",
        ],
    ),
    page(
        "Contact High Guacamole",
        "contact-high-guacamole",
        ingredients=["avocados", "lime", "jalapeño", "cilantro", "white onion", "salt"],
        steps=["Mash the avocados with lime and salt, then fold in the chopped onion, jalapeño and cilantro."],
    ),
    page(
        "Game Day Chili",
        "game-day-chili",
        description="Every football Sunday at our house. Doubled for the playoffs.",
        ingredients=[
            "2 lb ground beef",
            "1 onion, diced",
            "2 cans kidney beans",
            "1 can diced tomatoes",
            "2 tbsp chili powder",
            "1 tbsp cumin",
        ],
        steps=[
            "Brown the beef with the onion. Stir in the spices, then the beans and tomatoes with their liquid.",
            "Simmer at least an hour, the longer the better.",
        ],
    ),
    page(
        "New Year's Day Black-Eyed Peas",
        "new-years-day-black-eyed-peas",
        ingredients=["dried black-eyed peas", "ham hock", "onion", "garlic", "bay leaf"],
        steps=["Soak the peas overnight, then simmer everything together for about 90 minutes until creamy."],
    ),
    page(
        "Simple Syrup",
        "simple-syrup",
        ingredients=["1 cup sugar", "1 cup water"],
        steps=["Heat until the sugar dissolves. Cool and refrigerate up to a month."],
    ),
    page(
        "Garlic Butter",
        "garlic-butter",
        ingredients=["butter", "garlic"],
        steps=["Mash softened butter with grated garlic."],
    ),
    page(
        "Iced Coffee",
        "iced-coffee-cold-brew",
        ingredients=["coarse ground coffee", "cold water"],
        steps=["Steep 1 cup grounds in 4 cups water in the fridge for 12 to 18 hours, then strain and serve over ice."],
    ),
    page(
        "Caprese Sandwich",
        "caprese-sandwich",
        ingredients=["ciabatta", "fresh mozzarella", "tomato", "basil", "balsamic glaze"],
        steps=["Layer it all on the bread, drizzle with balsamic, and press it closed."],
    ),
    page(
        "Our Thanksgiving Turkey",
        "our-thanksgiving-turkey",
        description=(
            "Every year my whole family drives up to my parents' place in the mountains for Thanksgiving, "
            "and every year I'm in charge of the bird. This is the dry brine method I've used for eight years."
        ),
        ingredients=["1 (14 lb) turkey", "1/2 cup kosher salt", "2 tbsp brown sugar", "1 tbsp black pepper",
                     "1 stick butter, melted"],
        steps=[
            "Three days ahead, mix the salt, sugar and pepper and rub it all over the turkey. Refrigerate uncovered.",
            "On the day, heat the oven to 425°F. Brush with butter and roast 30 minutes.",
            "Lower to 325°F and roast until the thigh reads 165°F, about 2 1/2 more hours. Rest 30 minutes.",
        ],
        recipeYield="12 servings",
        totalTime="PT3H30M",
    ),
    page(
        "Sunday Morning Pancakes",
        "sunday-morning-pancakes",
        ingredients=[
            parsed(1.5, "cup", "flour"),
            parsed(3.5, "teaspoon", "baking powder"),
            parsed(1, "tablespoon", "sugar"),
            parsed(1.25, "cup", "milk"),
            parsed(1, None, "egg"),
            parsed(3, "tablespoon", "butter", "melted"),
        ],
        steps=["Whisk it all together and cook 1/4 cup portions on a buttered griddle until bubbles form, then flip."],
    ),
    page(
        "Cucumber Salad",
        "cucumber-salad-quick",
        ingredients=["cucumbers", "rice vinegar", "sugar", "sesame seeds"],
        steps=["Slice the cucumbers thin, toss with vinegar, a pinch of sugar and sesame seeds. Let sit 10 minutes."],
    ),
    page(
        "Hot Toddy",
        "hot-toddy",
        ingredients=["whiskey", "honey", "lemon", "hot water", "cinnamon stick"],
        steps=["Stir the whiskey and honey into a mug of hot water, squeeze in lemon, add the cinnamon stick."],
    ),
    page(
        "Christmas Morning Cinnamon Rolls",
        "christmas-morning-cinnamon-rolls",
        description="I make the dough on Christmas Eve and bake them while the kids open stockings.",
        ingredients=[
            "4 cups flour",
            "1 packet instant yeast",
            "1 cup warm milk",
            "1/3 cup sugar",
            "1/3 cup butter",
            "2 eggs",
            "Filling: 1 cup brown sugar, 2 tbsp cinnamon, 1/3 cup soft butter",
            "Icing: 4 oz cream cheese, 1 cup powdered sugar",
        ],
        steps=[
            "Mix the dough ingredients and knead 5 minutes. Let rise 1 hour.",
            "Roll out into a rectangle, spread with filling, roll up, and cut into 12 rolls.",
            "Place in a buttered pan, cover, and refrigerate overnight.",
            "In the morning, let them sit 30 minutes, then bake at 350°F for 25 minutes. Ice while warm.",
        ],
        recipeYield="12 rolls",
    ),
    page(
        "Shop Talk Shrimp Tacos",
        "shop-talk-shrimp-tacos",
        ingredients=["shrimp", "chili powder", "corn tortillas", "cabbage", "lime crema"],
        steps=[
            "Toss the shrimp with chili powder and sear in a hot pan about 2 minutes. Pile into warm "
            "tortillas with cabbage and a drizzle of crema.",
        ],
    ),
    page(
        "Grandma's Story Bread",
        "grandmas-story-bread",
        description=(
            "My grandmother came over from Poland in 1952 with almost nothing, and she baked this bread every "
            "Saturday of her life. She never wrote it down. I spent a whole summer standing next to her with "
            "a notebook and a measuring cup, catching handfuls before they went in the bowl."
        ),
        ingredients=["flour", "water", "yeast", "salt", "caraway seeds"],
        steps=[
            "Grandma just said: mix until it feels right, let it rise until it's doubled, shape it, let it "
            "rise again, and bake in a hot oven until it sounds hollow when you knock on the bottom. In my "
            "notebook that works out to about 4 cups flour, 1 1/2 cups water, a packet of yeast, 2 teaspoons "
            "salt, a tablespoon of caraway, and 40 minutes at 400 degrees.",
        ],
    ),
    page(
        "Welcome Drink",
        "welcome-drink",
        ingredients=["prosecco", "elderflower liqueur", "lemon twist"],
        steps=["Pour a splash of elderflower into a flute and top with prosecco."],
    ),
    page(
        "Peanut Butter Banana Toast",
        "peanut-butter-banana-toast",
        ingredients=["toast", "peanut butter", "banana", "honey"],
        steps=["Spread, slice, drizzle. Done."],
    ),
    page(
        "Weeknight Fried Rice",
        "weeknight-fried-rice",
        ingredients=["leftover rice", "eggs", "frozen peas and carrots", "soy sauce", "green onions", "sesame oil"],
        steps=[
            "Honestly I just get the pan really hot with some oil, scramble a couple of eggs and push them to "
            "the side, then dump in the cold rice and the frozen veg and keep it moving for a few minutes. A "
            "good splash of soy, a little sesame oil at the end, and green onions on top.",
        ],
    ),
    page(
        "Lemonade",
        "lemonade-fresh",
        ingredients=[
            parsed(1, "cup", "lemon juice", "fresh"),
            parsed(1, "cup", "simple syrup"),
            parsed(4, "cup", "cold water"),
        ],
        steps=["Stir together in a pitcher and serve over ice."],
        recipeYield="6 cups",
    ),
    page(
        "Tailgate Guide Pulled Pork",
        "tailgate-guide-pulled-pork",
        description="My complete guide to feeding a crowd at the stadium parking lot.",
        ingredients=["pork shoulder", "brown sugar", "paprika", "garlic powder", "BBQ sauce", "slider buns"],
        steps=[
            "Rub the pork with sugar, paprika and garlic powder.",
            "Slow cook on low 10 hours, then shred and mix with BBQ sauce.",
            "Pack in a cooler-safe container and serve on buns.",
        ],
    ),
    page(
        "Apple Cider Sangria",
        "apple-cider-sangria",
        ingredients=["apple cider", "white wine", "brandy", "sliced apples", "cinnamon sticks"],
        steps=["Combine in a pitcher and chill for a few hours so the fruit soaks it up."],
    ),
]

CORPUS = [(p, "junk") for p in JUNK] + [(p, "recipe") for p in RECIPES]
