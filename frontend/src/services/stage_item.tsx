import assert from 'assert';
import { SWRResponse } from 'swr';

import { responseIsValid } from '../components/utils/util';
import { StageWithStageItems } from '../interfaces/stage';
import {
  StageItemInputCreateBody,
  StageItemInputOption,
  formatStageItemInput,
} from '../interfaces/stage_item_input';
import { Tournament } from '../interfaces/tournament';
import { createAxios, getAvailableStageItemInputs, handleRequestError } from './adapter';

export async function createStageItem(
  tournament_id: number,
  stage_id: number,
  type: string,
  team_count: number,
  inputs: StageItemInputCreateBody[]
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/stage_items`, { stage_id, type, team_count, inputs })
    .catch((response: any) => handleRequestError(response));
}

export async function updateStageItem(tournament_id: number, stage_item_id: number, name: string) {
  return createAxios()
    .put(`tournaments/${tournament_id}/stage_items/${stage_item_id}`, { name })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteStageItem(tournament_id: number, stage_item_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/stage_items/${stage_item_id}`)
    .catch((response: any) => handleRequestError(response));
}

export function getAvailableInputs(
  tournament: Tournament,
  stageId: number,
  teamsMap: {
    [p: string]: any;
  },
  stageItemMap: { [p: string]: any }
) {
  const swrAvailableInputsResponse: SWRResponse = getAvailableStageItemInputs(
    tournament.id,
    stageId
  );
  const availableInputs = responseIsValid(swrAvailableInputsResponse)
    ? swrAvailableInputsResponse.data.data.map((option: StageItemInputOption) => {
        if (option.winner_from_stage_item_id == null) {
          if (option.team_id == null) return null;
          const team = teamsMap[option.team_id];
          if (team == null) return null;
          return {
            value: `${option.team_id}`,
            label: team.name,
          };
        }
        assert(option.winner_position != null);
        const stageItem = stageItemMap[option.winner_from_stage_item_id];
        if (stageItem == null) return null;
        return {
          value: `${option.winner_from_stage_item_id}_${option.winner_position}`,
          label: `${formatStageItemInput(option.winner_position, stageItem.name)}`,
        };
      })
    : {};
  return availableInputs;
}
