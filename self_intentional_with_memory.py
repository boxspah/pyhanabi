import random

from hanabi import (
    Player,
    HINT_COLOR,
    whattodo,
    HINT_NUMBER,
    ALL_COLORS,
    format_intention,
    DISCARD,
    PLAY,
    Action,
    get_possible,
    playable,
    discardable,
    pretend,
    COLORNAMES,
    format_knowledge,
    pretend_discard,
    f,
    Intent,
)


def _intent_unchanged(old: Intent | None, new: Intent | None) -> bool:
    return old == new or (old == Intent.PLAY and new is None)


class SelfIntentionalPlayerWithMemory(Player):
    def __init__(self, name, pnr):
        super().__init__(name)
        self.pnr = pnr
        self.gothint = None
        self.last_knowledge = []
        self.last_played = []
        self.last_board = []
        self._intents_conveyed: list[Intent | None] = [
            None for _ in range(self._hand_size)
        ]

    def get_action(
        self, nr, hands, knowledge, trash, played, board, valid_actions, hints
    ):
        handsize = len(knowledge[0])
        possible = []
        result = None
        self.explanation = []
        self.explanation.append(["Your Hand:"] + list(map(f, hands[1 - nr])))
        action = []
        if self.gothint:
            (act, plr) = self.gothint
            if act.type == HINT_COLOR:
                for k in knowledge[nr]:
                    action.append(whattodo(k, sum(k[act.col]) > 0, board))
            elif act.type == HINT_NUMBER:
                for k in knowledge[nr]:
                    cnt = 0
                    for c in ALL_COLORS:
                        cnt += k[c][act.num - 1]
                    action.append(whattodo(k, cnt > 0, board))

        if action:
            self.explanation.append(
                ["What you want me to do"] + list(map(format_intention, action))
            )
            for i, a in enumerate(action):
                if a == PLAY and (not result or result.type == DISCARD):
                    result = Action(PLAY, cnr=i)
                elif a == DISCARD and not result:
                    result = Action(DISCARD, cnr=i)

        self.gothint = None
        for k in knowledge[nr]:
            possible.append(get_possible(k))

        discards = []
        for i, p in enumerate(possible):
            if playable(p, board) and not result:
                result = Action(PLAY, cnr=i)
            if discardable(p, board):
                discards.append(i)

        if discards and hints < 8 and not result:
            result = Action(DISCARD, cnr=random.choice(discards))

        intentions: list[Intent] = self.generate_intents(board, hands, nr, trash)

        self.explanation.append(
            ["Intentions"] + list(map(format_intention, intentions))
        )

        if hints > 0:
            result = self.give_hint(board, hands, intentions, knowledge, nr, result)

        self.explanation.append(
            ["My Knowledge"] + list(map(format_knowledge, knowledge[nr]))
        )
        possible = [Action(DISCARD, cnr=i) for i in list(range(handsize))]

        scores = list(
            map(lambda p: pretend_discard(p, knowledge[nr], board, trash), possible)
        )

        def format_term(x):
            (col, rank, _, prob, val) = x
            return (
                COLORNAMES[col]
                + " "
                + str(rank)
                + " (%.2f%%): %.2f" % (prob * 100, val)
            )

        self.explanation.append(
            ["Discard Scores"]
            + list(
                map(
                    lambda x: "\n".join(map(format_term, x[2])) + "\n%.2f" % (x[1]),
                    scores,
                )
            )
        )
        scores.sort(key=lambda x: -x[1])
        if result:
            return result
        return scores[0][0]

    def generate_intents(self, board, hands, nr, trash) -> list[Intent]:
        playables = []
        useless = []
        discardables = []
        othercards = trash + board
        intentions = [Intent.KEEP for _ in range(self._hand_size)]

        for i, h in enumerate(hands):
            if i != nr:
                for j, (col, n) in enumerate(h):
                    if board[col][1] + 1 == n:
                        playables.append((i, j))
                        intentions[j] = Intent.PLAY
                    elif board[col][1] >= n:
                        useless.append((i, j))
                        intentions[j] = Intent.DISCARD
                    elif n < 5 and (col, n) not in othercards:
                        discardables.append((i, j))
                        intentions[j] = Intent.CAN_DISCARD

        return intentions

    def give_hint(self, board, hands, intentions, knowledge, nr, result) -> Action:
        valid: list[tuple[tuple[int, int], int, list[int | None]]] = []
        for c in ALL_COLORS:
            action = (HINT_COLOR, c)
            # print("HINT", COLORNAMES[c],)
            (isvalid, score, expl) = pretend(
                action, knowledge[1 - nr], intentions, hands[1 - nr], board
            )

            if isvalid and all(
                _intent_unchanged(self._intents_conveyed[i], expl[i])
                for i in range(len(self._intents_conveyed))
            ):
                isvalid = False
                score = 0
                expl = ["No new intentions"]

            self.explanation.append(
                ["Prediction for: Hint Color " + COLORNAMES[c]]
                + list(map(format_intention, expl))
            )
            # print(isvalid, score)
            if isvalid:
                assert all(isinstance(x, int) or x is None for x in expl)
                valid.append((action, score, expl))
        for r in range(5):
            r += 1
            action = (HINT_NUMBER, r)
            # print("HINT", r,)

            (isvalid, score, expl) = pretend(
                action, knowledge[1 - nr], intentions, hands[1 - nr], board
            )

            if isvalid and all(
                _intent_unchanged(self._intents_conveyed[i], expl[i])
                for i in range(len(self._intents_conveyed))
            ):
                isvalid = False
                score = 0
                expl = ["No new intentions"]

            self.explanation.append(
                ["Prediction for: Hint Rank " + str(r)]
                + list(map(format_intention, expl))
            )
            # print(isvalid, score)
            if isvalid:
                assert all(isinstance(x, int) or x is None for x in expl)
                valid.append((action, score, expl))
        if valid and not result:
            valid.sort(key=lambda x: x[1], reverse=True)
            # print(valid)
            (a, s, expl) = valid[0]

            # I assume that result will not be mutated after this block and in the calling code
            if a[0] == HINT_COLOR:
                result = Action(HINT_COLOR, pnr=1 - nr, col=a[1])
            else:
                result = Action(HINT_NUMBER, pnr=1 - nr, num=a[1])

            self._intents_conveyed = [
                self._intents_conveyed[i]
                if expl[i] is None and self._intents_conveyed[i] == PLAY
                else expl[i]
                for i in range(len(expl))
            ]
        return result

    def _rotate_intents(self, removed_cnr: int) -> None:
        for i in range(removed_cnr, len(self._intents_conveyed) - 1):
            self._intents_conveyed[i] = self._intents_conveyed[i + 1]
        self._intents_conveyed[-1] = None

    def inform(self, action, player, game):
        if action.type in [PLAY, DISCARD] and action.pnr != self.pnr:
            self._rotate_intents(action.cnr)

        elif action.pnr == self.pnr:
            self.gothint = (action, player)
            self.last_knowledge = game.knowledge[:]
            self.last_board = game.board[:]
            self.last_trash = game.trash[:]
            self.played = game.played[:]
