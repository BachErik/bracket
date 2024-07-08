import math
from collections import defaultdict
from decimal import Decimal
from typing import TypeVar

from bracket.database import database
from bracket.models.db.match import MatchWithDetailsDefinitive
from bracket.models.db.players import START_ELO, PlayerStatistics
from bracket.models.db.ranking import Ranking
from bracket.models.db.util import StageItemWithRounds
from bracket.schema import players, teams
from bracket.sql.players import get_all_players_in_tournament, update_player_stats
from bracket.sql.rankings import get_ranking_for_stage_item
from bracket.sql.stage_items import get_stage_item
from bracket.sql.teams import get_teams_in_tournament, update_team_stats
from bracket.utils.id_types import PlayerId, StageItemId, TeamId, TournamentId
from bracket.utils.types import assert_some

K = 32
D = 400


TeamIdOrPlayerId = TypeVar("TeamIdOrPlayerId", bound=PlayerId | TeamId)


def set_statistics_for_player_or_team(
    team_index: int,
    stats: defaultdict[TeamIdOrPlayerId, PlayerStatistics],
    match: MatchWithDetailsDefinitive,
    team_or_player_id: TeamIdOrPlayerId,
    rating_team1_before: float,
    rating_team2_before: float,
    ranking: Ranking,
) -> None:
    is_team1 = team_index == 0
    team_score = match.team1_score if is_team1 else match.team2_score
    was_draw = match.team1_score == match.team2_score
    has_won = not was_draw and team_score == max(match.team1_score, match.team2_score)

    if has_won:
        stats[team_or_player_id].wins += 1
        swiss_score_diff = ranking.win_points
    elif was_draw:
        stats[team_or_player_id].draws += 1
        swiss_score_diff = ranking.draw_points
    else:
        stats[team_or_player_id].losses += 1
        swiss_score_diff = ranking.loss_points

    if ranking.add_score_points:
        swiss_score_diff += match.team1_score if is_team1 else match.team2_score

    stats[team_or_player_id].swiss_score += swiss_score_diff

    rating_diff = (rating_team2_before - rating_team1_before) * (1 if is_team1 else -1)
    expected_score = Decimal(1.0 / (1.0 + math.pow(10.0, rating_diff / D)))
    stats[team_or_player_id].elo_score += int(K * (swiss_score_diff - expected_score))


def determine_ranking_for_stage_item(
    stage_item: StageItemWithRounds,
    ranking: Ranking,
) -> tuple[defaultdict[PlayerId, PlayerStatistics], defaultdict[TeamId, PlayerStatistics]]:
    player_x_stats: defaultdict[PlayerId, PlayerStatistics] = defaultdict(PlayerStatistics)
    team_x_stats: defaultdict[TeamId, PlayerStatistics] = defaultdict(PlayerStatistics)
    matches = [
        match
        for round_ in stage_item.rounds
        if not round_.is_draft
        for match in round_.matches
        if isinstance(match, MatchWithDetailsDefinitive)
        if match.team1_score != 0 or match.team2_score != 0
    ]
    for match in matches:
        rating_team1_before = (
            sum(player_x_stats[player_id].elo_score for player_id in match.team1.player_ids)
            / len(match.team1.player_ids)
            if len(match.team1.player_ids) > 0
            else START_ELO
        )
        rating_team2_before = (
            sum(player_x_stats[player_id].elo_score for player_id in match.team2.player_ids)
            / len(match.team2.player_ids)
            if len(match.team2.player_ids) > 0
            else START_ELO
        )

        for team_index, team in enumerate(match.teams):
            if team.id is not None:
                set_statistics_for_player_or_team(
                    team_index,
                    team_x_stats,
                    match,
                    team.id,
                    rating_team1_before,
                    rating_team2_before,
                    ranking,
                )

            for player in team.players:
                set_statistics_for_player_or_team(
                    team_index,
                    player_x_stats,
                    match,
                    assert_some(player.id),
                    rating_team1_before,
                    rating_team2_before,
                    ranking,
                )

    return player_x_stats, team_x_stats


async def determine_team_ranking_for_stage_item(
    stage_item: StageItemWithRounds,
    ranking: Ranking,
) -> list[tuple[TeamId, PlayerStatistics]]:
    _, team_ranking = determine_ranking_for_stage_item(stage_item, ranking)
    return sorted(team_ranking.items(), key=lambda x: x[1].elo_score, reverse=True)


async def recalculate_ranking_for_stage_item_id(
    tournament_id: TournamentId,
    stage_item_id: StageItemId,
) -> None:
    stage_item = await get_stage_item(tournament_id, stage_item_id)
    ranking = await get_ranking_for_stage_item(tournament_id, stage_item_id)
    assert stage_item, "Stage item not found"
    assert ranking, "Ranking not found"

    determine_ranking_for_stage_item(assert_some(stage_item), assert_some(ranking))


async def todo_recalculate_ranking_for_stage_items(
    tournament_id: TournamentId, stage_item: StageItemWithRounds, ranking: Ranking
) -> None:
    elo_per_player, elo_per_team = determine_ranking_for_stage_item(stage_item, ranking)

    for player_id, statistics in elo_per_player.items():
        await update_player_stats(tournament_id, player_id, statistics)

    for team_id, statistics in elo_per_team.items():
        await update_team_stats(tournament_id, team_id, statistics)

    all_players = await get_all_players_in_tournament(tournament_id)
    for player in all_players:
        if player.id not in elo_per_player:
            await database.execute(
                query=players.update().where(
                    (players.c.id == player.id) & (players.c.tournament_id == tournament_id)
                ),
                values=PlayerStatistics().model_dump(),
            )

    all_teams = await get_teams_in_tournament(tournament_id)
    for team in all_teams:
        if team.id not in elo_per_team:
            await database.execute(
                query=teams.update().where(
                    (teams.c.id == team.id) & (teams.c.tournament_id == tournament_id)
                ),
                values=PlayerStatistics().model_dump(),
            )
