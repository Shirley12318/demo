from models import db_session, Location, Question, StoryEvent
import json

def load_initial_data(app):
    with app.app_context():
        if db_session.query(Location).count() > 0:
            print("数据已存在，跳过初始化...")
            return

        print("正在初始化韶山红色文化数据...")

        locations = [
            {
                'name': '毛泽东故居',
                'description': '位于韶山市韶山乡韶山村土地冲上屋场的普通农舍。1893年12月26日，毛泽东诞生在这里，并在此度过了童年和少年时代。',
                'is_landmark': True,
                'cultural_significance': '这里是毛泽东主席诞生的地方，见证了中国革命伟大领袖的成长历程。'
            },
            {
                'name': '韶山学校',
                'description': '韶山学校前身为韶山乡私立学校，毛泽东曾在此接受启蒙教育。学校位于韶山冲，是韶山地区重要的教育场所。',
                'is_landmark': True,
                'cultural_significance': '代表着毛泽东追求知识、探索真理的求学精神。'
            },
            {
                'name': '韶山烈士陵园',
                'description': '为纪念韶山革命烈士而建立的纪念园，安葬着韶山地区为中国革命牺牲的烈士。烈士陵园庄严肃穆，是缅怀先烈的重要场所。',
                'is_landmark': True,
                'cultural_significance': '体现了韶山人民的革命精神和为人民解放事业献身的崇高品质。'
            },
            {
                'name': '滴水洞',
                'description': '滴水洞是毛泽东青少年时期读书和生活的地方，位于韶山冲西部。这里环境幽静，是毛泽东思考中国革命问题的重要场所。',
                'is_landmark': True,
                'cultural_significance': '见证了毛泽东从学生到革命家的思想转变过程。'
            },
            {
                'name': '韶山毛氏宗祠',
                'description': '毛氏宗祠是毛氏家族祭祀祖先的场所，也是毛泽东早年接受家族文化教育的地方。宗祠保存了大量毛氏家族的历史文物。',
                'is_landmark': False,
                'cultural_significance': '体现了中国传统家族文化和革命精神的传承关系。'
            },
            {
                'name': '银田寺',
                'description': '银田寺是韶山地区的重要历史遗迹，也是毛泽东早期革命活动的地点之一。1925年，毛泽东曾在此开展农民运动。',
                'is_landmark': True,
                'cultural_significance': '这里是毛泽东领导农民运动、播撒革命火种的重要地点。'
            },
            {
                'name': '风云亭',
                'description': '风云亭是韶山景区的重要景点，纪念毛泽东在此眺望祖国山河、思考国家命运的历史。登亭远眺，可以俯瞰韶山冲全景。',
                'is_landmark': False,
                'cultural_significance': '象征着毛泽东心怀天下、志在四方的伟大抱负。'
            },
            {
                'name': '青年水库',
                'description': '青年水库是韶山地区的重要水利工程，体现了韶山人民自力更生、艰苦奋斗的精神。水库建于上世纪50年代，是韶山人民战天斗地的杰作。',
                'is_landmark': False,
                'cultural_significance': '代表着韶山人民改天换地、建设美好家园的奋斗精神。'
            }
        ]

        for loc_data in locations:
            location = Location(**loc_data)
            db_session.add(location)

        db_session.flush()
        print(f"已加载 {len(locations)} 个地点")

        questions = [
            {"question": "毛泽东主席出生于哪一年？", "options": ["1890年", "1893年", "1896年", "1900年"], "correct_answer": 1, "difficulty": 1, "category": "历史", "explanation": "毛泽东主席于1893年12月26日出生于湖南省湘潭县韶山冲。"},
            {"question": "毛泽东主席的故乡在哪里？", "options": ["长沙", "韶山", "湘潭", "浏阳"], "correct_answer": 1, "difficulty": 1, "category": "历史", "explanation": "毛泽东主席的故乡是湖南省湘潭县韶山冲，现为韶山市。"},
            {"question": "韶山是哪个省的著名革命纪念地？", "options": ["江西", "湖南", "湖北", "四川"], "correct_answer": 1, "difficulty": 1, "category": "历史", "explanation": "韶山位于湖南省湘潭市，是著名的革命纪念地和旅游景区。"},
            {"question": "毛泽东在韶山度过了多长时间？", "options": ["5年", "10年", "17年", "20年"], "correct_answer": 2, "difficulty": 2, "category": "历史", "explanation": "毛泽东在韶山度过了童年和少年时代，大约17年，直到1910年离开韶山外出求学。"},
            {"question": "1925年，毛泽东在韶山开展了什么运动？", "options": ["学生运动", "工人运动", "农民运动", "妇女运动"], "correct_answer": 2, "difficulty": 2, "category": "历史", "explanation": "1925年，毛泽东回到韶山开展农民运动，这是他早期革命活动的重要组成部分。"},
            {"question": "韶山毛氏宗祠位于哪个位置？", "options": ["韶山冲上部", "韶山冲中部", "韶山冲下部", "韶山冲外部"], "correct_answer": 1, "difficulty": 2, "category": "地点", "explanation": "毛氏宗祠位于韶山冲中部，是毛氏家族祭祀祖先的场所。"},
            {"question": "以下哪个不是韶山的主要景点？", "options": ["毛泽东故居", "滴水洞", "橘子洲头", "韶山烈士陵园"], "correct_answer": 2, "difficulty": 1, "category": "地点", "explanation": "橘子洲头位于长沙，不是韶山的景点。"},
            {"question": "滴水洞因什么而得名？", "options": ["洞顶滴水不断", "洞内潮湿", "洞外形似滴水", "传说中滴水成洞"], "correct_answer": 0, "difficulty": 2, "category": "地点", "explanation": "滴水洞的洞顶有水滴不断滴落，常年不息，因此得名。"},
            {"question": "毛泽东故居位于韶山哪个村？", "options": ["韶山村", "银田村", "如意村", "永义村"], "correct_answer": 0, "difficulty": 2, "category": "地点", "explanation": "毛泽东故居位于韶山乡韶山村土地冲上屋场。"},
            {"question": "韶山烈士陵园主要纪念的是谁？", "options": ["毛泽东一家", "韶山籍革命烈士", "所有革命烈士", "抗日战争烈士"], "correct_answer": 1, "difficulty": 2, "category": "历史", "explanation": "韶山烈士陵园主要纪念为革命牺牲的韶山籍烈士。"},
            {"question": "毛泽东的母亲叫什么名字？", "options": ["毛文氏", "贺母", "文七妹", "杨氏"], "correct_answer": 2, "difficulty": 2, "category": "人物", "explanation": "毛泽东的母亲叫文七妹，是一位勤劳善良的农村妇女。"},
            {"question": "毛泽东的父亲叫什么名字？", "options": ["毛顺生", "毛贻昌", "毛德臣", "毛仁厚"], "correct_answer": 1, "difficulty": 2, "category": "人物", "explanation": "毛泽东的父亲叫毛贻昌，字顺生，是一位勤俭持家的农民。"},
            {"question": "毛泽东在韶山学校读书时的老师是谁？", "options": ["李大钊", "陈独秀", "邹春培", "周恩来"], "correct_answer": 2, "difficulty": 3, "category": "人物", "explanation": "邹春培是毛泽东在韶山学校读书时的老师。"},
            {"question": "毛泽东的亲密战友和同学是谁？", "options": ["周恩来", "朱德", "蔡和森", "刘少奇"], "correct_answer": 2, "difficulty": 2, "category": "人物", "explanation": "蔡和森是毛泽东在湖南第一师范学校读书时的同学和亲密战友。"},
            {"question": "以下哪位不是韶山籍革命烈士？", "options": ["毛泽东", "杨开慧", "蔡和森", "向警予"], "correct_answer": 0, "difficulty": 3, "category": "人物", "explanation": "毛泽东是韶山人，但不是烈士。杨开慧、蔡和森、向警予都是为革命牺牲的烈士。"},
            {"question": "毛泽东离开韶山外出求学的年份是？", "options": ["1905年", "1908年", "1910年", "1912年"], "correct_answer": 2, "difficulty": 2, "category": "历史", "explanation": "1910年，17岁的毛泽东离开韶山，前往湘乡县立东山高等小学堂求学。"},
            {"question": "韶山精神的核心是什么？", "options": ["自强不息", "艰苦奋斗", "无私奉献", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "精神", "explanation": "韶山精神包括自力更生、艰苦奋斗、无私奉献等多个方面。"},
            {"question": "毛泽东故居被称为什么？", "options": ["红色圣地", "革命摇篮", "伟人故居", "以上都是"], "correct_answer": 3, "difficulty": 1, "category": "历史", "explanation": "毛泽东故居被称为红色圣地、革命摇篮、伟人故居，是重要的革命纪念地。"},
            {"question": "1966年，毛泽东重访韶山的主要目的是什么？", "options": ["探亲", "休养", "考察", "以上都不是"], "correct_answer": 2, "difficulty": 3, "category": "历史", "explanation": "1966年，毛泽东回到韶山，主要是为了考察和了解基层情况。"},
            {"question": "韶山地区共有多少位正式登记在册的革命烈士？", "options": ["100多位", "200多位", "300多位", "400多位"], "correct_answer": 1, "difficulty": 3, "category": "历史", "explanation": "韶山地区有200多位革命烈士为革命事业献出了宝贵生命。"},
            {"question": "银田寺在韶山革命历史中有什么重要意义？", "options": ["毛泽东曾在此讲学", "毛泽东曾在此开展农运", "中共韶山支部成立地", "革命烈士就义地"], "correct_answer": 1, "difficulty": 3, "category": "历史", "explanation": "1925年，毛泽东在银田寺一带开展农民运动，播撒革命火种。"},
            {"question": "毛泽东在韶山读私塾时，最喜欢读什么书？", "options": ["《论语》", "《水浒传》", "《三国演义》", "《诗经》"], "correct_answer": 2, "difficulty": 3, "category": "历史", "explanation": "毛泽东少年时最喜欢读《水浒传》和《三国演义》等古典小说。"},
            {"question": "韶山毛氏家族的辈分排序中，毛泽东属于哪一辈？", "options": ["祖", "泽", "toh", "远"], "correct_answer": 1, "difficulty": 3, "category": "历史", "explanation": "毛泽东属于'泽'字辈，名'泽东'。"},
            {"question": "毛泽东的故乡韶山冲共有多少户人家？", "options": ["几十户", "上百户", "几百户", "上千户"], "correct_answer": 1, "difficulty": 3, "category": "地点", "explanation": "韶山冲是一个小山村，过去有上百户人家，是一个典型的南方农村。"},
            {"question": "韶山滴水洞现有哪三部分建筑群？", "options": ["大屋、楼房、别墅", "平房、亭子、寺庙", "学校、祠堂、陵园", "以上都不是"], "correct_answer": 0, "difficulty": 3, "category": "地点", "explanation": "滴水洞现有大屋、楼房、别墅三部分建筑群。"},
            {"question": "毛泽东在韶山少年时期从事过什么劳动？", "options": ["放牛", "砍柴", "种田", "以上都有"], "correct_answer": 3, "difficulty": 1, "category": "历史", "explanation": "毛泽东少年时期帮助家里放牛、砍柴、种田等，经历了艰苦的劳动生活。"},
            {"question": "韶山学校的前身是什么？", "options": ["私塾", "公立小学", "私立学校", "教会学校"], "correct_answer": 2, "difficulty": 2, "category": "历史", "explanation": "韶山学校前身为韶山乡私立学校，由毛宇居等人创办。"},
            {"question": "毛泽东的七律诗《七律·到韶山》写作于哪一年？", "options": ["1949年", "1959年", "1966年", "1976年"], "correct_answer": 2, "difficulty": 3, "category": "历史", "explanation": "1959年，毛泽东回到阔别32年的韶山，写下了《七律·到韶山》。"},
            {"question": "《七律·到韶山》中'别梦依稀咒逝川'的下一句是什么？", "options": ["故园三十二年前", "红旗卷起农奴戟", "为有牺牲多壮志", "敢教日月换新天"], "correct_answer": 0, "difficulty": 3, "category": "历史", "explanation": "下一句是'故园三十二年前'，这句诗表达了毛泽东对故乡的深厚感情。"},
            {"question": "韶山红色文化的核心精神是什么？", "options": ["敢为人先", "百折不挠", "无私奉献", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "精神", "explanation": "韶山精神包括敢为人先、百折不挠、无私奉献等丰富的精神内涵。"},
            {"question": "学习韶山红色文化的主要意义是什么？", "options": ["了解历史", "传承精神", "激励奋斗", "以上都是"], "correct_answer": 3, "difficulty": 1, "category": "精神", "explanation": "学习韶山红色文化有助于了解革命历史、传承红色精神、激励当代奋斗。"},
            {"question": "毛泽东从韶山走出后，首先去了哪所学校求学？", "options": ["湖南第一师范", "湘乡东山小学", "长沙第一中学", "北京大学"], "correct_answer": 1, "difficulty": 2, "category": "历史", "explanation": "1910年，毛泽东首先去了湘乡县立东山高等小学堂求学。"},
            {"question": "毛泽东在韶山度过了他的什么时期？", "options": ["童年和少年", "青年", "中年", "老年"], "correct_answer": 0, "difficulty": 1, "category": "历史", "explanation": "毛泽东在韶山度过了童年和少年时期，直到1910年外出求学。"},
            {"question": "韶山革命烈士陵园内建有什么纪念设施？", "options": ["纪念碑", "陈列馆", "烈士墓", "以上都有"], "correct_answer": 3, "difficulty": 2, "category": "地点", "explanation": "陵园内有纪念碑、陈列馆、烈士墓等纪念设施。"},
            {"question": "毛泽东少年时期在韶山形成的最重要品质是什么？", "options": ["勤俭节约", "吃苦耐劳", "志向远大", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "精神", "explanation": "韶山的艰苦生活培养了毛泽东勤俭节约、吃苦耐劳、志向远大的品质。"},
            {"question": "滴水洞别墅始建于什么时间？", "options": ["1950年代", "1960年代", "1970年代", "1980年代"], "correct_answer": 1, "difficulty": 3, "category": "历史", "explanation": "滴水洞别墅建于1960年代，是专为毛泽东休养而建造的。"},
            {"question": "韶山成为中国著名红色旅游景点的意义是什么？", "options": ["纪念伟人", "传承文化", "教育后人", "以上都是"], "correct_answer": 3, "difficulty": 1, "category": "精神", "explanation": "韶山作为红色旅游景点，具有纪念伟人、传承文化、教育后人的重要意义。"},
            {"question": "毛泽东在韶山少年时期最敬佩的人是谁？", "options": ["父亲", "母亲", "老师", "农民"], "correct_answer": 1, "difficulty": 2, "category": "人物", "explanation": "毛泽东少年时期最敬佩的母亲文七妹，她的勤劳善良对毛泽东影响很深。"},
            {"question": "1927年，毛泽东考察湖南农民运动时回到韶山，他对农民运动的评价是？", "options": ["糟得很", "好得很", "一般", "不知道"], "correct_answer": 1, "difficulty": 3, "category": "历史", "explanation": "毛泽东在《湖南农民运动考察报告》中高度赞扬农民运动'好得很'。"},
            {"question": "韶山毛氏家族在近代出了多少位革命烈士？", "options": ["几位", "十几位", "二十多位", "五十多位"], "correct_answer": 2, "difficulty": 3, "category": "历史", "explanation": "韶山毛氏家族有二十多位革命烈士，为中国革命作出了重大牺牲。"},
            {"question": "毛泽东的哪篇文章是在韶山实地调查后写成的？", "options": ["《实践论》", "《矛盾论》", "《湖南农民运动考察报告》", "《论持久战》"], "correct_answer": 2, "difficulty": 3, "category": "历史", "explanation": "1927年，毛泽东实地考察了湖南农民运动后写成了《湖南农民运动考察报告》。"},
            {"question": "韶山精神与什么精神一脉相承？", "options": ["井冈山精神", "延安精神", "长征精神", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "精神", "explanation": "韶山精神与井冈山精神、延安精神、长征精神等都是中国共产党革命精神的重要组成部分。"},
            {"question": "毛泽东在韶山读小学时，给同学留下了什么印象？", "options": ["调皮捣蛋", "勤奋好学", "胆小怕事", "沉默寡言"], "correct_answer": 1, "difficulty": 2, "category": "人物", "explanation": "毛泽东在韶山读小学时给同学留下了勤奋好学、才华出众的印象。"},
            {"question": "韶山滴⽔洞最深的洞窟叫什么？", "options": ["上洞", "中洞", "下洞", "底洞"], "correct_answer": 2, "difficulty": 3, "category": "地点", "explanation": "滴水洞最深的洞窟是下洞，深不可测，有着许多传说。"},
            {"question": "毛泽东少年时在韶山最喜欢做什么事？", "options": ["读书", "劳动", "游泳", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "历史", "explanation": "毛泽东少年时喜欢读书、劳动和游泳，尤其热爱阅读各种书籍。"},
            {"question": "韶山在中国革命史上的地位是什么？", "options": ["革命圣地", "伟人故里", "精神家园", "以上都是"], "correct_answer": 3, "difficulty": 1, "category": "历史", "explanation": "韶山是革命圣地、伟人故里、精神家园，在中国革命史上具有重要地位。"},
            {"question": "为什么说韶山是'红太阳升起的地方'？", "options": ["日出东方", "毛泽东诞生于此", "革命火种源自这里", "以上都是"], "correct_answer": 3, "difficulty": 2, "category": "历史", "explanation": "因为毛泽东诞生于此，革命火种源自这里，中国走向光明，故称'红太阳升起的地方'。"},
            {"question": "青年水库建于什么年代？", "options": ["1940年代", "1950年代", "1960年代", "1970年代"], "correct_answer": 1, "difficulty": 2, "category": "历史", "explanation": "青年水库建于1950年代，是韶山人民自力更生、艰苦奋斗的象征。"},
            {"question": "韶山毛氏宗祠供奉的是谁？", "options": ["毛泽东", "毛氏历代祖先", "革命烈士", "历史名人"], "correct_answer": 1, "difficulty": 2, "category": "地点", "explanation": "毛氏宗祠供奉的是毛氏家族的历代祖先。"},
            {"question": "以下哪项不是韶山精神的内涵？", "options": ["艰苦奋斗", "实事求是", "奢靡享乐", "为人民服务"], "correct_answer": 2, "difficulty": 1, "category": "精神", "explanation": "奢靡享乐不是韶山精神的内涵，韶山精神强调艰苦奋斗、实事求是、为人民服务。"},
            {"question": "毛泽东主席的诞生地是？", "options": ["北京", "上海", "韶山", "长沙"], "correct_answer": 2, "difficulty": 1, "category": "人物", "explanation": "毛泽东主席于1893年12月26日诞生于湖南省湘潭县韶山冲。"},
            {"question": "韶山烈士陵园的主题雕塑是为了纪念什么？", "options": ["建军", "建党", "革命烈士", "长征"], "correct_answer": 2, "difficulty": 2, "category": "历史", "explanation": "韶山烈士陵园的主题雕塑是为了纪念为中国革命牺牲的韶山籍烈士。"}
        ]

        for q_data in questions:
            question = Question(
                question=q_data['question'],
                options=json.dumps(q_data['options']),
                correct_answer=q_data['correct_answer'],
                difficulty=q_data['difficulty'],
                category=q_data['category'],
                explanation=q_data['explanation']
            )
            db_session.add(question)

        db_session.flush()
        print(f"已加载 {len(questions)} 道知识问答题目")

        story_events = [
            {"title": "韶山诞生", "description": "1893年12月26日，在湖南省湘潭县韶山冲的一个普通农民家庭里，一个男婴哇哇坠地。父母给他取名毛泽东，字润之。这个偏僻的小山村，从这一天起，便与中国人民的命运紧密联系在了一起。", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "为毛泽东的诞生感到欣喜", "rewards": {"gold": 0, "experience": 20, "energy": 0, "reputation": 5}, "result": "你的心中涌起对这位未来伟人的敬仰之情。", "knowledge": "毛泽东的诞生，标志着中国革命即将迎来一位伟大的领路人。"},
                {"index": 1, "text": "思考这个家庭未来的命运", "rewards": {"gold": 0, "experience": 15, "energy": 0, "reputation": 3}, "result": "一个普通农民家庭，将培养出改变中国命运的人。", "knowledge": "家庭环境和成长经历对一个人的品格形成有重要影响。"}
            ]), "required_experience": 0},

            {"title": "韶山求学", "description": "1902年，年仅9岁的毛泽东开始在家乡的私塾读书。他先后在韶山的几所私塾就读，师从邹春培等老师。少年毛泽东聪明好学，尤其喜欢阅读《水浒传》《三国演义》等古典小说，常常沉浸在这些英雄故事中。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "认真诵读经典诗文", "rewards": {"gold": 0, "experience": 25, "energy": -5, "reputation": 5}, "result": "你仿佛看到少年毛泽东在私塾里勤奋读书的身影。", "knowledge": "扎实的基础教育为毛泽东日后的博学多才奠定了基础。"},
                {"index": 1, "text": "阅读《水浒传》等小说", "rewards": {"gold": 0, "experience": 20, "energy": 0, "reputation": 3}, "result": "这些英雄故事一定在少年毛泽东心中种下了救国救民的种子。", "knowledge": "阅读能够开阔视野，培养人的品格和志向。"}
            ]), "required_experience": 0},

            {"title": "少年立志", "description": "一天，毛泽东在劳动之余，望着连绵的韶山群山，陷入了沉思。他对父亲说：'我要走出韶山，去看看外面的世界，去学习救国救民的道理。'父亲起初不理解，但最终被儿子的坚定打动。", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "支持毛泽东外出求学的决定", "rewards": {"gold": 0, "experience": 30, "energy": 0, "reputation": 10}, "result": "一个伟大的决定，将改变中国革命的进程。", "knowledge": "追求知识、探索真理是青年人应有的品质。"},
                {"index": 1, "text": "劝说毛泽东留在家中帮忙", "rewards": {"gold": 10, "experience": -10, "energy": -5, "reputation": -3}, "result": "虽然务农也很重要，但外面的世界需要他去闯荡。", "knowledge": "小家与大家的抉择，考验着每个人的胸怀。"}
            ]), "required_experience": 20},

            {"title": "田间劳动", "description": "少年时期的毛泽东经常帮助家里干农活。无论是放牛、砍柴还是下田耕作，他都积极参与。艰苦的劳动生活锻炼了他的体魄，也让他深知农民的辛苦，这为他日后提出'农村包围城市'的革命道路埋下了伏笔。", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "敬佩毛泽东的勤劳品质", "rewards": {"gold": 0, "experience": 25, "energy": 5, "reputation": 5}, "result": "勤劳是中华民族的传统美德，也是革命者的基本品质。", "knowledge": "劳动创造价值，劳动人民最光荣。"},
                {"index": 1, "text": "思考劳动与革命的关系", "rewards": {"gold": 0, "experience": 30, "energy": 0, "reputation": 8}, "result": "革命就是为了让劳动人民过上好日子。", "knowledge": "革命的目的就是解放生产力，让人民当家作主。"}
            ]), "required_experience": 0},

            {"title": "离开韶山", "description": "1910年，17岁的毛泽东即将离开家乡，前往湘乡县立东山高等小学堂求学。临行前，他给父亲写了一首诗：'孩儿立志出乡关，学不成名誓不还。埋骨何须桑梓地，人生无处不青山。'这首诗表达了他求学的决心和远大的志向。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "为毛泽东的远大志向感动", "rewards": {"gold": 0, "experience": 35, "energy": 0, "reputation": 10}, "result": "从韶山走向全中国，从这里开始了他波澜壮阔的革命生涯。", "knowledge": "立志是成功的起点，有志者事竟成。"},
                {"index": 1, "text": "理解离别家乡的心情", "rewards": {"gold": 0, "experience": 25, "energy": 5, "reputation": 5}, "result": "每一次离别，都是为了更好的归来。", "knowledge": "家乡是永远的牵挂，革命者也有儿女情长。"}
            ]), "required_experience": 30},

            {"title": "东山求教", "description": "毛泽东来到湘乡东山小学堂后，如饥似渴地学习新知识。在这里，他第一次接触到西方政治思想和科学文化知识。他勤奋好学的精神给老师和同学留下了深刻的印象，也在这里结识了许多志同道合的朋友。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "感叹新式学堂的教育", "rewards": {"gold": 0, "experience": 30, "energy": 0, "reputation": 8}, "result": "新式教育开阔了毛泽东的视野，让他看到了更广阔的世界。", "knowledge": "教育是改变命运的重要途径。"},
                {"index": 1, "text": "敬佩毛泽东的学习精神", "rewards": {"gold": 0, "experience": 35, "energy": -5, "reputation": 10}, "result": "刻苦学习是革命者的本色。", "knowledge": "活到老学到老，这是毛泽东一生的追求。"}
            ]), "required_experience": 40},

            {"title": "湘乡求学", "description": "在湘乡学习期间，毛泽东不仅刻苦钻研学业，还积极参加体育锻炼。他常常在清晨跑步锻炼身体，深信'文明其精神，野蛮其体魄'的道理。这段经历让他明白了体育锻炼对革命事业的重要性。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "重视体育锻炼", "rewards": {"gold": 0, "experience": 25, "energy": 10, "reputation": 5}, "result": "强健的体魄是革命的本钱。", "knowledge": "身体是革命的本钱，体育锻炼很重要。"},
                {"index": 1, "text": "理解精神与体魄的关系", "rewards": {"gold": 0, "experience": 30, "energy": 5, "reputation": 8}, "result": "精神与体魄全面发展，才能担当大任。", "knowledge": "德智体美劳全面发展，是毛泽东一贯的教育思想。"}
            ]), "required_experience": 50},

            {"title": "省城求学", "description": "1913年，毛泽东考入湖南省立第四师范学校，后并入湖南第一师范学校。在这里，他遇到了恩师杨昌济、徐特立等良师，也结识了蔡和森、陈潭秋等志同道合的战友。他广泛阅读各类书籍，寻求救国救民的真理。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "敬佩毛泽东的求知欲", "rewards": {"gold": 0, "experience": 35, "energy": 0, "reputation": 10}, "result": "广泛阅读让毛泽东成为学识渊博的革命家。", "knowledge": "知识就是力量，学习使人进步。"},
                {"index": 1, "text": "理解交友的重要性", "rewards": {"gold": 0, "experience": 30, "energy": 0, "reputation": 8}, "result": "良师益友是人生宝贵的财富。", "knowledge": "近朱者赤，近墨者黑，交友要谨慎。"}
            ]), "required_experience": 60},

            {"title": "组织新民学会", "description": "1918年，毛泽东和蔡和森等人组织成立了新民学会。这是中国早期进步青年的组织之一，以'改造中国与世界'为宗旨。新民学会的许多成员后来都成为中国共产党的早期党员和革命骨干。", "location_id": 2, "choices": json.dumps([
                {"index": 0, "text": "支持进步青年的组织", "rewards": {"gold": 0, "experience": 40, "energy": 0, "reputation": 15}, "result": "青年是革命的主力军。", "knowledge": "团结就是力量，青年人要勇于担当。"},
                {"index": 1, "text": "思考组织的意义", "rewards": {"gold": 0, "experience": 35, "energy": 0, "reputation": 10}, "result": "有组织的青年力量能够改变中国。", "knowledge": "组织起来，才能发挥更大的力量。"}
            ]), "required_experience": 70},

            {"title": "革命火种", "description": "1925年，已经成为马克思主义者的毛泽东回到韶山。他深入农户，宣传革命道理，组织农民协会。在短短几个月时间里，韶山地区的农民运动蓬勃发展，为后来的革命斗争播下了火种。", "location_id": 6, "choices": json.dumps([
                {"index": 0, "text": "支持农民运动", "rewards": {"gold": 0, "experience": 45, "energy": -10, "reputation": 20}, "result": "农民是中国革命的主力军。", "knowledge": "农民运动是中国革命的重要组成部分。"},
                {"index": 1, "text": "敬佩毛泽东的组织能力", "rewards": {"gold": 0, "experience": 40, "energy": 0, "reputation": 15}, "result": "从群众中来，到群众中去，这是毛泽东的伟大之处。", "knowledge": "密切联系群众，是革命胜利的保障。"}
            ]), "required_experience": 80},

            {"title": "考察农民运动", "description": "1927年，毛泽东回到湖南考察农民运动。他走村串户，深入调研，写出了著名的《湖南农民运动考察报告》。这篇报告高度赞扬了农民运动'好得很'，为中国共产党领导农民运动提供了理论指导。", "location_id": 6, "choices": json.dumps([
                {"index": 0, "text": "进行实地调研", "rewards": {"gold": 0, "experience": 50, "energy": -10, "reputation": 20}, "result": "没有调查就没有发言权。", "knowledge": "实事求是是毛泽东思想的精髓。"},
                {"index": 1, "text": "重视农民的力量", "rewards": {"gold": 0, "experience": 45, "energy": 0, "reputation": 15}, "result": "农民占中国人口的绝大多数，是革命的重要力量。", "knowledge": "谁赢得了农民，谁就赢得了中国。"}
            ]), "required_experience": 90},

            {"title": "韶山情怀", "description": "新中国成立后，毛泽东虽然日理万机，但始终思念着韶山。1959年，他终于回到阔别32年的故乡。他感慨万千，写下了著名的诗篇《七律·到韶山》，表达了对故土的深情和对革命先烈的缅怀。", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "朗诵毛泽东的诗篇", "rewards": {"gold": 0, "experience": 50, "energy": 5, "reputation": 20}, "result": "'别梦依稀咒逝川，故园三十二年前'，多么深情的诗句！", "knowledge": "革命者也有浓浓的乡情。"},
                {"index": 1, "text": "感悟革命者的情怀", "rewards": {"gold": 0, "experience": 45, "energy": 0, "reputation": 15}, "result": "无论走多远，故乡永远是心中最柔软的地方。", "knowledge": "不忘初心，方得始终。"}
            ]), "required_experience": 100},

            {"title": "缅怀先烈", "description": "1959年，毛泽东在韶山烈士陵园，深情缅怀为革命牺牲的韶山籍烈士。他说：'为了革命，韶山牺牲了多少人呐！'他亲自邀请烈士家属吃饭，向他们敬酒，表达对先烈们的崇高敬意。", "location_id": 3, "choices": json.dumps([
                {"index": 0, "text": "向革命先烈致敬", "rewards": {"gold": 0, "experience": 55, "energy": 0, "reputation": 25}, "result": "革命先烈用鲜血和生命换来了今天的幸福生活。", "knowledge": "吃水不忘挖井人，我们要永远铭记革命先烈。"},
                {"index": 1, "text": "传承先烈精神", "rewards": {"gold": 0, "experience": 50, "energy": 5, "reputation": 20}, "result": "继承先烈遗志，将革命进行到底。", "knowledge": "革命精神代代相传，这是对先烈最好的纪念。"}
            ]), "required_experience": 110},

            {"title": "重访韶山", "description": "1966年，毛泽东再次回到韶山。这次回到故乡，他更加感慨。在滴水洞，他居住了十多天，思考着中国革命和建设的重大问题。韶山对于毛泽东来说，是永远的精神家园。", "location_id": 4, "choices": json.dumps([
                {"index": 0, "text": "感受领袖的乡愁", "rewards": {"gold": 0, "experience": 55, "energy": 5, "reputation": 20}, "result": "即使身为国家领袖，依然思念着故乡。", "knowledge": "故乡是每个人精神的根和魂。"},
                {"index": 1, "text": "思考革命与建设", "rewards": {"gold": 0, "experience": 60, "energy": -5, "reputation": 25}, "result": "革命成功了，但建设新中国的任务更艰巨。", "knowledge": "革命是破旧立新，建设是筑梦未来。"}
            ]), "required_experience": 120},

            {"title": "毛氏家风", "description": "在韶山毛氏宗祠，毛泽东了解了毛氏家族的历史。毛氏家族世代勤劳朴实，乐善好施。良好的家风家训对毛泽东的成长产生了深远影响。他后来提出的'为人民服务'思想，与毛氏家族的家风一脉相承。", "location_id": 5, "choices": json.dumps([
                {"index": 0, "text": "重视家风传承", "rewards": {"gold": 0, "experience": 50, "energy": 0, "reputation": 20}, "result": "良好的家风是人生的宝贵财富。", "knowledge": "家风正则民风淳，民风淳则社稷安。"},
                {"index": 1, "text": "理解为人民服务思想", "rewards": {"gold": 0, "experience": 55, "energy": 0, "reputation": 25}, "result": "从家族的爱推及到对人民的爱，这是毛泽东思想的升华。", "knowledge": "家国情怀，是中华民族的优良传统。"}
            ]), "required_experience": 130},

            {"title": "青年水库", "description": "1950年代，韶山人民在党的领导下，自力更生，艰苦奋斗，修建了青年水库。毛泽东听说后非常高兴，他说：'人民群众的力量是无穷的。'青年水库成为韶山人民战天斗地的历史见证。", "location_id": 8, "choices": json.dumps([
                {"index": 0, "text": "赞叹人民群众的力量", "rewards": {"gold": 0, "experience": 55, "energy": 0, "reputation": 20}, "result": "只要团结起来，人民群众就能创造奇迹。", "knowledge": "人民是历史的创造者，是真正的英雄。"},
                {"index": 1, "text": "学习艰苦奋斗精神", "rewards": {"gold": 0, "experience": 60, "energy": 5, "reputation": 25}, "result": "自力更生、艰苦奋斗是中华民族的精神基因。", "knowledge": "艰难困苦，玉汝于成。"}
            ]), "required_experience": 140},

            {"title": "红色传承", "description": "如今的韶山，每年都吸引着无数游客前来参观学习。人们在这里缅怀革命先烈，接受红色教育。韶山精神正在一代代传承，激励着人们为实现中华民族伟大复兴的中国梦而努力奋斗。", "location_id": 3, "choices": json.dumps([
                {"index": 0, "text": "立志传承红色精神", "rewards": {"gold": 0, "experience": 65, "energy": 0, "reputation": 30}, "result": "红色基因代代传，我们是社会主义事业的接班人！", "knowledge": "传承红色基因，赓续精神血脉。"},
                {"index": 1, "text": "为实现中国梦而奋斗", "rewards": {"gold": 0, "experience": 70, "energy": 0, "reputation": 35}, "result": "不忘初心，牢记使命，为实现中华民族伟大复兴而努力！", "knowledge": "中国梦是历史的、现实的，也是未来的。"}
            ]), "required_experience": 150},

            {"title": "韶山精神", "description": "韶山精神的核心是'为有牺牲多壮志，敢教日月换新天'。它包括：坚定信念、敢为人先的创新精神；实事求是、开拓进取的科学态度；不怕牺牲、百折不挠的革命意志；心系人民、热爱人民的赤子情怀。", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "深入学习韶山精神", "rewards": {"gold": 0, "experience": 70, "energy": 5, "reputation": 30}, "result": "韶山精神是中国共产党的宝贵精神财富。", "knowledge": "精神的力量是无穷的，能够激励人们克服一切困难。"},
                {"index": 1, "text": "将韶山精神融入日常", "rewards": {"gold": 0, "experience": 65, "energy": 0, "reputation": 25}, "result": "让韶山精神成为我们行动的指南。", "knowledge": "学而时习之，将精神力量转化为实际行动。"}
            ]), "required_experience": 160},

            {"title": "革命理想", "description": "回顾毛泽东在韶山的岁月，我们看到的是一个农村少年如何通过学习和奋斗，最终成为伟大的革命家。他的经历告诉我们：只有把个人理想融入国家和民族的伟大事业中，才能成就人生的最大价值。", "location_id": 4, "choices": json.dumps([
                {"index": 0, "text": "树立远大理想", "rewards": {"gold": 0, "experience": 75, "energy": 0, "reputation": 35}, "result": "少年强则国强，少年智则国智！", "knowledge": "理想信念是精神之'钙'，没有理想信念就会缺钙。"},
                {"index": 1, "text": "为国家民族而奋斗", "rewards": {"gold": 0, "experience": 80, "energy": 0, "reputation": 40}, "result": "功成不必在我，功成必定有我！", "knowledge": "一代人有一代人的使命，一代人有一代人的担当。"}
            ]), "required_experience": 170},

            {"title": "永远的韶山", "description": "韶山，这片红色的土地，孕育了伟大的领袖，也孕育了伟大的精神。无论我们身在何处，都不应忘记这片土地上的革命故事和红色精神。韶山精神将永远激励着我们前行！", "location_id": 1, "choices": json.dumps([
                {"index": 0, "text": "铭记韶山精神", "rewards": {"gold": 0, "experience": 80, "energy": 10, "reputation": 40}, "result": "韶山精神，永放光芒！", "knowledge": "红色文化是我们宝贵的精神遗产。"},
                {"index": 1, "text": "做红色传人", "rewards": {"gold": 0, "experience": 85, "energy": 5, "reputation": 45}, "result": "传承红色基因，争做时代新人！", "knowledge": "让红色基因代代相传，让革命事业薪火相传。"}
            ]), "required_experience": 180}
        ]

        for event_data in story_events:
            event = StoryEvent(
                title=event_data['title'],
                description=event_data['description'],
                location_id=event_data['location_id'],
                choices=event_data['choices'],
                required_experience=event_data['required_experience']
            )
            db_session.add(event)

        db_session.flush()
        print(f"已加载 {len(story_events)} 个剧情事件")

        db_session.commit()
        print("\n韶山红色文化数据初始化完成！")
        print("=" * 50)
