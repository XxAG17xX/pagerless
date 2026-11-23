import {Composition} from "remotion";
import {Pagerless} from "./Pagerless";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition id="Pagerless" component={Pagerless} durationInFrames={1920} fps={30} width={1920} height={1080} />
  );
};
