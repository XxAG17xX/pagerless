import {Composition} from "remotion";
import {Pagerless, SECONDS} from "./Pagerless";

export const RemotionRoot: React.FC = () => {
  return <Composition id="Pagerless" component={Pagerless} durationInFrames={SECONDS * 60} fps={60} width={1920} height={1080} />;
};
