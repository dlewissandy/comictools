from enum import StrEnum
from pydantic import BaseModel, Field
from style.comic import ComicStyle
from models.issue import Issue
from models.character import CharacterModel
from models.series import Series

    
if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    #style = ComicStyle.generate("Rankin-Bass stop-motion animation style.")

    #character = CharacterModel.read("brassic", variant="gnome-disguise")
    #rugor = CharacterModel.read("rugor")

    # character.render(style = ComicStyle.read("childlike-crayon"))
    # character.render(style = ComicStyle.read("claymation"))
    #character.render(style = ComicStyle.read("concept-sketch")) 
    #character.render(style = ComicStyle.read("conte-crayon"))
    # character.render(style = ComicStyle.read("film-noir"))
    # character.render(style = ComicStyle.read("hyper-realism"))
    # character.render(style = ComicStyle.read("modern-anime"))
    # character.render(style = ComicStyle.read("pixar"))
    # character.render(style = ComicStyle.read("saturday-morning"))
    #character.render(style = ComicStyle.read("vintage-four-color"))
    #character.render(style = ComicStyle.read("watercolor")) 
    #character.render(style = ComicStyle.read("van-gogh"))
    #character.render(style = ComicStyle.read("neolithic"))
    #character.render(style = ComicStyle.read("rankin-bass-stop-motion"))
    #rugor.render(style = ComicStyle.read("rankin-bass-stop-motion"))
    
    series = Series(series_title="Wonders of the Witchlight", publisher="DND Nerds", logo=None)
    series.write()
    
    joe = series.generate_character("Joe", "A young child (age 3 or 4) who really wants do do things on his own, but who struggles with those challenges.   He is clever and resourceful, and takes pride in his ability to solve problems.   He does not care much about his appearance, and often has toussled sandy blonde hair and messy attire.   Today he is wearing a red t-shirt with shorts and socks without shoes.    His left sock is starting to come off.")
    
    issue1 = series.add_issue(issue_title="Witchlight Carnival")
    issue2 = series.add_issue(issue_title="Hither")
    issue3 = series.add_issue(issue_title="Thither")
    issue4 = series.add_issue(issue_title="Yon")
    print(series.issues)
    
    scene = issue1.generate_scene("""
Four adventurers are drawn to the Witchlight Carnival.   We learn that they each have been to the carnival before, having snuck in to see the sights.   Each is yearning to find a part of themselves that was lost at their last visit.   When they arrive, they find tickets awiting for them, and a fifth companion, a gnome guide who will tour them through the carnival.   But all is not as it seems." 
""")
    
    

    # comic.revise_beatboards("Lets add some panels at the beginning where Joe discovers that he is hungry and decides to make a sandwich.   Lets also make sure that dog is in all the frames (e.g. peeking over the counter when Joe is making the sandwich).",0)
    # comic.revise_beatboards("Make sure that there are panels where Joe gets each of the ingredients out of the cupboard.   He might need to get a stool first",0)
    # comic.revise_beatboards("Make sure that the panels where joe is opening a container (jar of peanut butter, jar of jam, bag of bread) are separate from the panel where he uses it.",0)
    # comic.revise_beatboards("The final panel should be mom cleaning up in the background while Joe is eating his second sandwich.  Dog is nearby hoping for crumbs.",0)
    
    # print(comic.scenes[0].format())

    #comic.translate_beatboards(index=0)
    # print(comic.scenes[0].format())
    